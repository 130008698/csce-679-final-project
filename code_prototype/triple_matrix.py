import spacy
import scispacy
import json
import pdb
import re

from spacy.matcher import Matcher
from scispacy.linking import EntityLinker
from tqdm import tqdm


def get_complete_word(txt: str, start: int, end: int):
    if txt[start] == ' ':
        start += 1
        before = ' '
    else:
        before = txt[start - 1] if start != 0 else ' '

    after = txt[end] if end < len(txt) - 1 else ' '

    if before.isspace() and after.isspace():
        return txt[start:end]

    if before != ' ':
        while start > 0 and txt[start - 1].isalnum() or txt[start - 1] in {'-', '_', "'"}:
            start -= 1

    if after != ' ':
        while end < len(txt) and txt[end].isalnum() or txt[end] in {'-', '_', "'"}:
            end += 1
            if end == len(txt):
                break

    return txt[start:end]


def is_abbreviation(phrase: str, candidate: str):
    candidate = candidate.lower()
    phrase = phrase.lower()
    words = [word for word in phrase.replace('-', ' ').split()]

    candidate_idx = 0
    for word in words:
        if candidate_idx < len(candidate) and word[0] == candidate[candidate_idx]:
            candidate_idx += 1
        if candidate_idx == len(candidate) - 1:
            return True
    return False


def delete_repetition(txt: str):
    txt_list = txt.split(' ')
    unique_word = list(dict.fromkeys(txt_list))
    return ' '.join(unique_word)


def remove_shorter_substrings(strings: list):
    strings = sorted(strings, key=len, reverse=True)
    output = []

    for s in strings:
        if not any(s in longer for longer in output):
            output.append(s)
    return output


def extract_entities(txt: str, ner_list: list):
    pathogenesis = {'BIOLOGICAL_ATTRIBUTE', 'OTHER_ENTITY'}
    disease_label = {'DISEASE_DISORDER'}
    symptom_label = {'SIGN_SYMPTOM'}
    drug_label = {'MEDICATION', 'ADMINISTRATION'}

    patho, diseases, symptoms, drugs = [], [], [], []

    description = ''
    for ner in ner_list:
        if ner['entity_group'] == 'DETAILED_DESCRIPTION':
            description += get_complete_word(txt, ner['start'], ner['end']) + ' '

        else:
            if ner['entity_group'] in pathogenesis:
                cur = get_complete_word(txt, ner['start'], ner['end'])
                if patho and is_abbreviation(patho[-1], cur):
                    prev = patho.pop()
                    full_title = prev if not description else f'{description}{prev}'
                    standard = delete_repetition(f'{full_title} ({cur})')

                    standard_entity_names[full_title] = standard
                    standard_entity_names[cur] = standard

                    patho.append(standard)
                else:
                    new = f'{description}{cur}'
                    new = delete_repetition(new)
                    if new in standard_entity_names:
                        new = standard_entity_names[new]
                    patho.append(new)

            elif ner['entity_group'] in disease_label:
                cur = get_complete_word(txt, ner['start'], ner['end'])
                if diseases and is_abbreviation(diseases[-1], cur):
                    prev = diseases.pop()
                    full_title = prev if not description else f'{description}{prev}'
                    standard = delete_repetition(f'{full_title} ({cur})')

                    standard_entity_names[full_title] = standard
                    standard_entity_names[cur] = standard

                    diseases.append(standard)
                else:
                    new = f'{description}{cur}'
                    new = delete_repetition(new)
                    if new in standard_entity_names:
                        new = standard_entity_names[new]
                    diseases.append(new)

            elif ner['entity_group'] in symptom_label:
                cur = get_complete_word(txt, ner['start'], ner['end'])
                if symptoms and is_abbreviation(symptoms[-1], cur):
                    prev = symptoms.pop()
                    full_title = prev if not description else f'{description}{prev}'
                    standard = delete_repetition(f'{full_title} ({cur})')

                    standard_entity_names[full_title] = standard
                    standard_entity_names[cur] = standard

                    symptoms.append(standard)
                else:
                    new = f'{description}{cur}'
                    new = delete_repetition(new)
                    if new in standard_entity_names:
                        new = standard_entity_names[new]
                    symptoms.append(new)

            elif ner['entity_group'] in drug_label:
                cur = get_complete_word(txt, ner['start'], ner['end'])
                if drugs and is_abbreviation(drugs[-1], cur):
                    prev = drugs.pop()
                    full_title = prev if not description else f'{description}{prev}'
                    standard = delete_repetition(f'{full_title} ({cur})')

                    standard_entity_names[full_title] = standard
                    standard_entity_names[cur] = standard

                    drugs.append(standard)
                else:
                    new = f'{description}{cur}'
                    new = delete_repetition(new)
                    if new in standard_entity_names:
                        new = standard_entity_names[new]
                    drugs.append(new)

            description = ''

    patho = remove_shorter_substrings(patho)
    diseases = remove_shorter_substrings(diseases)
    symptoms = remove_shorter_substrings(symptoms)
    drugs = remove_shorter_substrings(drugs)

    return patho, diseases, symptoms, drugs


def dependence_relationships(txt: str):
    global sub_spans
    nlp_doc = nlp(txt)
    check_list = ['symptom', 'article', 'that', 'which', 'this', 'these', 'those']

    # extract subject
    sub_spans = []
    for token in nlp_doc:
        if token.dep_ == 'nsubj' or token.dep_ == 'nsubjpass':
            start = min(t.i for t in token.subtree)
            end = max(t.i for t in token.subtree) + 1
            sub_span = nlp_doc[start: end].text
            if not any(substr in sub_span.lower() for substr in check_list):
                sub_spans.append(sub_span)

    # extract predicate
    root_span = None
    for token in nlp_doc:
        if token.dep_ == 'ROOT':
            root_span = token
            break
    if not root_span:
        return [], [], []

    # extract obj
    obj_spans = []
    for token in nlp_doc:
        if token.dep_ == 'pobj' or token.dep_ == 'dobj':
            if nlp_doc[token.left_edge.i].dep_ == 'case':
                start = token.left_edge.i + 1
            else:
                start = token.left_edge.i

            obj_span = nlp_doc[start:token.right_edge.i + 1].text

            if not any(substr in obj_span.lower() for substr in check_list):
                obj_spans.append(obj_span)

    if not obj_spans:
        # extract nmod
        nmod_spans = []
        for token in nlp_doc:
            if token.dep_ == 'nmod':
                if nlp_doc[token.left_edge.i].dep_ == 'case':
                    start = token.left_edge.i + 1
                else:
                    start = token.left_edge.i

                nmod_span = nlp_doc[start:token.right_edge.i + 1].text

                if not any(substr in nmod_span.lower() for substr in check_list):
                    nmod_spans.append(nmod_span)

        xcomp_token = None
        for child in root_span.children:
            if child.dep_ == 'xcomp':
                xcomp_token = child
                break

        root_span = root_span.text
        if xcomp_token:
            children = list(xcomp_token.children)
            if children:
                start = min(t.i for t in children)
                end = max(t.i for t in children) + 1
                root_span += f' {nlp_doc[start:end].text}'

        return sub_spans, root_span, nmod_spans

    else:
        return sub_spans, root_span.text, obj_spans


def generate_triples(txt: str, ner_list: list):
    lists = list(extract_entities(txt, ner_list))
    for i in range(len(lists)):
        lists[i] = [s.replace('*', '') for s in lists[i]]
    patho, diseases, symptoms, drugs = lists

    txt = txt.replace('*', '')
    txt = txt.replace('- ', '')
    pattern1 = r'^\s*\d+[\.\)\-]*\s*'
    txt = re.sub(pattern1, '', txt)
    triples = []

    if diseases and symptoms and drugs:
        for disease in diseases:
            for symptom in symptoms:
                triples.append([disease, 'causes', symptom])

        for drug in drugs:
            for symptom in symptoms:
                for disease in diseases:
                    triples.append([drug, f'relieves {symptom}', disease])

    elif patho and diseases:
        for p in patho:
            for diseases in diseases:
                triples.append([p, 'related to', diseases])

    # elif diseases and symptoms:
    #     for disease in diseases:
    #         for symptom in symptoms:
    #             if disease == symptom:
    #                 continue
    #             triples.append([disease, 'causes', symptom])

    elif diseases and drugs:
        for drug in drugs:
            for disease in diseases:
                triples.append([drug, 'treats', disease])

    elif any([patho, diseases, symptoms, drugs]):
        for sub_txt in txt.split('. '):
            subs, veb, objs = dependence_relationships(sub_txt)
            subs = remove_shorter_substrings(subs)
            objs = remove_shorter_substrings(objs)

            for i in range(len(subs)):
                if subs[i] in standard_entity_names:
                    subs[i] = standard_entity_names[subs[i]]

            for i in range(len(objs)):
                if objs[i] in standard_entity_names:
                    objs[i] = standard_entity_names[objs[i]]

            for sub in subs:
                for obj in objs:
                    triples.append([sub, veb, obj])
    return triples


doc = []
for i in range(0, 10):
    file_dir = f'C:/tamu/CSCE679/final_project/data/relationships/vLLm_{i}.json'
    with open(file_dir, 'r') as f:
        doc += json.load(f)
    f.close()

nlp = spacy.load('en_core_sci_lg')

standard_entity_names = {}

cadidates = {}
pattern = r'\d+\..*?(?=\n\d+\.|\Z)'
for i in tqdm(range(len(doc)), desc='Generating triples...'):
    cadidates[doc[i]['pmcID']] = []
    matches = re.findall(pattern, doc[i]['relationships'], re.DOTALL)
    text_list = [match.strip().replace('\n', '') for match in matches]
    if not text_list:
        text_list = doc[i]['relationships'].split('\n')

    for txt, ner_list in zip(text_list, doc[i]['NER']):
        cadidates[doc[i]['pmcID']] += generate_triples(txt, ner_list)
    #     print(f'Raw txt: {txt};\ntriples:{generate_triples(txt, ner_list)}\n\n')
    # pdb.set_trace()

triples_dict = {}
for key, val in tqdm(cadidates.items(), desc='Clear triples...'):
    triples_dict[key] = []
    for candidate in val:
        if (
            candidate in triples or
            len(candidate[0].split()) > 10 or
            len(candidate[1].split()) > 10 or
            len(candidate[2].split()) > 10 or
            candidate[0] == candidate[2] or
            candidate[2] in candidate[1]
        ):
            continue

        if candidate[0] in standard_entity_names:
            candidate[0] = standard_entity_names[candidate[0]]

        if candidate[2] in standard_entity_names:
            candidate[2] = standard_entity_names[candidate[2]]

        triples_dict[key].append([candidate[0], candidate[1], candidate[2]])

pdb.set_trace()

with open('data/triple_matrix/all_with_ID.json', 'w') as f:
    json.dump(triples_dict, f)

print(f'-------------------document saved successfully  -------------------')
