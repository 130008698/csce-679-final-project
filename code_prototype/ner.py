import re

from transformers import pipeline
from vllm import LLM, SamplingParams
from tqdm import tqdm

import warnings
import torch
import json
import pdb
import os


with open('data/relationships/vLLm.json', 'r') as f:
    text = json.load(f)
f.close()


warnings.filterwarnings('ignore')
os.environ["CUDA_VISIBLE_DEVICES"] = "2,3"
print(os.environ.get("CUDA_VISIBLE_DEVICES", None))

model_id = 'mistralai/Ministral-8B-Instruct-2410'

query = 'You are a medical expert. Extract medical entities from the given text. ' \
        'The medical entities you need to extract are disease, symptom and Drugs.' \
        'Only return entities you find. If the entity is not mentioned, return NaN' \
        'The answer should generated in the following format: ' \
        'Diseases: disease1, disease2, disease3. ' \
        'Symptoms: symptom1, symptom2, symptom3. ' \
        'Drugs: drug1, drug2, drug3.'

llm = LLM(model=model_id, tokenizer_mode='mistral', tensor_parallel_size=2)
sampling_params = SamplingParams(temperature=0.7, top_p=0.95, max_tokens=500)
pipe = pipeline('token-classification',  model="Clinical-AI-Apollo/Medical-NER", aggregation_strategy='simple')

entities = {}
for i in tqdm(range(50000, len(text))):
    relationships = text[i]['relationships'].replace('*', '')
    messages = [
        {
            "role": "system",
            "content": query
        },
        {
            'role': 'user',
            'content': 'Now here is the text you need to extract medical entities. Text:' + relationships
        }
    ]

    subdict = {'pmcID': text[i]['pmcID']}

    try:
        outputs = llm.chat(messages, sampling_params=sampling_params, use_tqdm=False)
        generated_text = outputs[0].outputs[0].text
        generated_text = generated_text.replace('*', '')

        if generated_text:
            diseases = re.search(r"Diseases:\s*(.*)", generated_text, re.IGNORECASE).group(1).split(',')
            symptoms = re.search(r"Symptoms:\s*(.*)", generated_text, re.IGNORECASE).group(1).split(',')
            drugs = re.search(r"Drugs:\s*(.*)", generated_text, re.IGNORECASE).group(1).split(',')

            for disease in diseases:
                if disease != 'NaN':
                    entities[disease] = 'D'

            for symptom in symptoms:
                if symptom != 'NaN':
                    entities[symptom] = 'S'

            for drug in drugs:
                if drug != 'NaN':
                    entities[drug] = 'M'
            # print(entities)

    except Exception as e:
        print(f'Jump the current error in {i}th text: {e}')
        torch.cuda.empty_cache()
        continue

    # pdb.set_trace()

with open('data/relationships/entities_1.json', 'w') as f:
    json.dump(entities, f)

print('———————————————————— Document is saved successfully ————————————————————')