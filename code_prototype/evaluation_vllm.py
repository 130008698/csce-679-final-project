from vllm import LLM, SamplingParams
from huggingface_hub import login
from transformers import AutoTokenizer
from tqdm import tqdm

import warnings
import torch
import json
import pdb
import os


login(token='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')
# access_token: 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

warnings.filterwarnings('ignore')
os.environ['CUDA_VISIBLE_DEVICES'] = '2,3'
print(os.environ.get("CUDA_VISIBLE_DEVICES", None))
# torch.distributed.destroy_process_group()

with open('data/summaries/vLLm_1.json', 'r') as f:
    summaries = json.load(f)
f.close()
#
# with open('data/relationships/vLLm_1.json', 'r') as f:
#     relationships = json.load(f)
# f.close()
# # pdb.set_trace()
#
# for i in range(len(summaries)):
#     if summaries[i]['pmcID'] != relationships[i]['pmcID']:
#         del summaries[i]
#         break
#
# for i in range(len(summaries)):
#     if summaries[i]['pmcID'] != relationships[i]['pmcID']:
#         print(i)
# pdb.set_trace()

with open('data/relationships/vLLm_1.json', 'r') as f:
    doc = json.load(f)
f.close()
torch.cuda.empty_cache()

model_id = 'Qwen/Qwen2.5-7B-Instruct'
# model_id = 'deepseek-ai/DeepSeek-R1-Distill-Llama-8B'
# model_id = 'meta-llama/Llama-3.1-8B-Instruct'
llm = LLM(model=model_id, tokenizer_mode='auto', tensor_parallel_size=2)
sampling_params = SamplingParams(temperature=0.7, top_p=0.8, repetition_penalty=1.05,max_tokens=512)

# query = 'You are an evaluator. There are a string of summary and a string of relationships extract from the summary.' \
#         'Check whether relationships are true according to the summary. If they are true, return 1, otherwise return 0.' \
#         'Only return scores.' \
query = 'You are a grader. There is a summary of an article and ' \
        'information containing medical entities and their relationships extract from the article.' \
        'Grade the accuracy of each information and score it from 0 ~ 100.' \
        '0 means completely inaccurate and 100 means totally accurate. Do not grade all information to zero' \
        'The answer should NOT contain any content in the given summary or relationships and only return scores.'


res = []
for i in tqdm(range(len(doc))):
    relationships = doc[i]['relationships'].replace('*', '')
    messages = [
        {
            "role": "system",
            "content": query
        },
        {
            "role": "user",
            "content": f'Summary: {summaries[i]["summary"]} Relationships: {relationships}.'
        },
    ]

    try:
        outputs = llm.chat(messages, sampling_params=sampling_params, use_tqdm=False)
        score = outputs[0].outputs[0].text
        # print(score)
        if score:
            # for deepseek
            # score = score.split('</think>', 1)
            # score = score[1].strip()
            # print(score)
            res += [{'pmcID': doc[i]['pmcID'], 'score': score}]
    except torch.cuda.OutOfMemoryError:
        print('Out of memory error encountered, skipping current pmcID: ' + doc[i]['pmcID'])
        torch.cuda.empty_cache()
        continue
    # pdb.set_trace()

with open('data/scores/Qwen_1.json', 'w') as f:
    json.dump(res, f)
print('———————————————————— Document is saved successfully ————————————————————')
