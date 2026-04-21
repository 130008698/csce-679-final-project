from statistics import mean
from tqdm import tqdm
import json
import pdb
import re


with open('data/scores/llama_1.json', 'r') as f:
    score_text = json.load(f)
    f.close()
# pdb.set_trace()

avgs = {}
# for i in tqdm(range(1000)):
for i in tqdm(range(len(score_text))):
    pattern = r'(?<![a-zA-Z-])\b\d+(\.\d+)?\b(?!\.\s|[a-zA-Z-])'
    scores = re.finditer(pattern, score_text[i]['score'])
    # s = [float(score.group()) for score in scores]
    # pdb.set_trace()
    s = []
    for score in scores:
        s_num = float(score.group())
        if s_num > 100:
            continue
        s.append(s_num)

    ################ test #######################
    if not s:
        # print(score_text[i]['score'])
        continue
    #############################################
    # if not s:
    #     continue
    avg = mean(s)
    avgs[i] = avg
    # pdb.set_trace()


overall_avg = mean(avgs.values())
print(overall_avg)
print(len(avgs))
# pdb.set_trace()