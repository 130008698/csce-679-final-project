from transformers import pipeline
from huggingface_hub import login, hf_hub_download
from datetime import datetime, timedelta
from vllm import LLM, SamplingParams
from tqdm import tqdm

import warnings
import torch
import json
import pdb
import os
import re


with open('data/relationships/0.json', 'r') as f:
    text = json.load(f)
f.close()
# pdb.set_trace()


warnings.filterwarnings('ignore')
os.environ["CUDA_VISIBLE_DEVICES"] = "0,1,2,3"
print(os.environ.get("CUDA_VISIBLE_DEVICES", None))

model_id = 'mistralai/Ministral-8B-Instruct-2410'

query1 = 'Summarize the article. ' \


query2 = 'Read the article, find the relationships between medical entities step by step.' \
         'Find the medical entities including ' \
         'pathogenesis (if mentioned), disease, symptoms and medications referred in the article' \
         'Use a single simple sentence to describe relationship between each mentioned entities, for example:' \
         '1. Cystic fibrosis transmembrane conductance regulator gene causes cystic fibrosis.' \
         '2. Pancreatic cancer causes high sensitivity to ferroptosis' \
         '3. Trimethoprim-sulfamethoxazole relieve fatigue caused by breast cancer' \
         'If no symptom is mentioned' \
         '4. Tamoxifen treats breast cancer'


llm = LLM(model=model_id, tokenizer_mode='mistral', tensor_parallel_size=4)
sampling_params = SamplingParams(temperature=0.7, top_p=0.95, max_tokens=500)
pipe = pipeline('token-classification',  model="Clinical-AI-Apollo/Medical-NER", aggregation_strategy='simple')

res = []
pattern = r'\d+\..*?(?=\n\d+\.|\Z)'
for i in tqdm(range(len(text))):
    messages1 = [
        {
            "role": "user",
            "content": query1 + text[i]['main_content']
        },
    ]

    messages2 = [
        {
            "role": "user",
            "content": query2 + text[i]['main_content']
        },
    ]
    subdict = {'pmcID': text[i]['pmcID']}

    try:
        outputs1 = llm.chat(messages1, sampling_params=sampling_params, use_tqdm=False)
        generated_text1 = outputs1[0].outputs[0].text
        outputs2 = llm.chat(messages2, sampling_params=sampling_params, use_tqdm=False)
        generated_text2 = outputs2[0].outputs[0].text

        if generated_text1 and generated_text2:
            subdict['summary'] = generated_text1
            subdict['relationships'] = generated_text2

            # use while extracting relationships
            matches = re.findall(pattern, generated_text2, re.DOTALL)
            text_list = [match.strip().replace('\n', '') for match in matches]
            if not text_list:
                text_list = generated_text2.split('\n')

            ner = pipe(text_list)
            subdict['NER'] = [
                [{'entity_group': item['entity_group'], 'word': item['word'],
                  'start': item['start'], 'end': item['end']} for item in sublist] for sublist in ner
            ]

            # print(generated_text2)
            res.append(subdict)

    except torch.cuda.OutOfMemoryError:
        print('Out of memory error encountered, skipping current batch: ' + str(i))
        torch.cuda.empty_cache()
        continue
    # pdb.set_trace()

# with open('data/summaries/vLLm_1.json', 'w') as f:
#     json.dump(res, f)

with open('data/relationships/vLLm_1_1.json', 'w') as f:
    json.dump(res, f)

print('———————————————————— Document is saved successfully ————————————————————')

# with open('data/full_text/0.json', 'r') as f:
#     text = json.load(f)

# with open('data/summaries/vLLm_0.json', 'r') as f:
#     text = json.load(f)

# pdb.set_trace()

# query = 'Summarize the article including all of the disease, symptom and drug referred in the article. ' \
#         'Please list all of the disease, symptom and drug you find.'
#
# query = 'Read the article, find the relationships between disease, symptoms and drugs referred in the article.' \
#         'There are three relationships:' \
#         '1. <disease> causes <symptom>, if symptom not referred in the article, ignore it; ' \
#         '2. <drug> treats/reduce/relieve <symptom>  <disease>; ' \
#         '3. <drug> treats/reduce/relieve <disease>, if symptom not referred in the article' \
#         'Only list the relationship between disease, symptom and drug you found.' \
#         'Here are some examples: ' \
#         '1. COVID-19<disease> | cause | fever<symptom>; ' \
#         '2. ibuprofen<drug> | treat | fever<symptom> | COVID-19<disease>'
#
#
# access_token = "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"
# # login(token=access_token)
# model_id = 'mistralai/Mistral-7B-Instruct-v0.2'
#
# tokenizer = AutoTokenizer.from_pretrained(
#         model_id,
#         padding_side='left',
#         cache_dir='/scratch',
#         trust_remote_code=True
#     )
# tokenizer.pad_token = tokenizer.eos_token
# tokenizer.padding_side = 'left'
# sampling_params = SamplingParams(
#     # temperature=0.7,
#     # top_p=0.95,
#     max_tokens=500)
# llm = LLM(model=model_id, tokenizer=model_id, tensor_parallel_size=4, dtype=torch.bfloat16)
#
#
# res = []
# for i in tqdm(range(len(text))):
#     # prompt = '<s>[INST] ' + query + text['main_content'][i] + '[/INST]</s>'
#     prompt = '<s>[INST] ' + query + text[i]['summary'] + '[/INST]</s>'
#     inputs = tokenizer(prompt, padding=False, return_tensors="pt").to('cuda')
#
#     try:
#         outputs =  llm.generate(prompt, sampling_params, use_tqdm=False)
#         generated_text = outputs[0].outputs[0].text
#         if generated_text:
#             # res += [{'pmcID': text['pmcID'][i], 'summary': generated_text}]
#             res += [{'pmcID': text[i]['pmcID'], 'relationships': generated_text}]
#     except torch.cuda.OutOfMemoryError:
#         print('Out of memory error encountered, skipping current batch: ' + str(i))
#         torch.cuda.empty_cache()
#         continue
#     # pdb.set_trace()
#     # print(f'Generated text: {generated_text!r}')
#
# # with open('data/summaries/vLLm_2.json', 'w') as f:
# #     json.dump(res, f)
#
# with open('data/relationships/vLLm_0.json', 'w') as f:
#     json.dump(res, f)
#
# print('——————————Document is saved successfully——————————')