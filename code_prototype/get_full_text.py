from Bio import Entrez
from lxml import etree
from tqdm import tqdm
import pandas as pd
import random
import json
import pdb
import os

def search_pmc(query, max_result=999999999):
    handle = Entrez.esearch(db='pmc', term=query, retmax=max_result)
    result = Entrez.read(handle)
    handle.close()
    return result['IdList']

def remove_figures_and_tables(section):
    for fig in section.findall('.//fig'):
        fig.getparent().remove(fig)
    for table in section.findall('.//table-wrap'):
        table.getparent().remove(table)
    return section

def extract_main_content(pmcID):
    try:
        handle = Entrez.efetch(db='pmc', id=pmcID, rettype='full', retmode='xml')
        record = handle.read()
        record = record.decode('utf-8')
        handle.close()

        # root = ET.fromstring(record)  # use xml.etree.ElementTree
        root = etree.fromstring(record)  # use lxml.etree
        article_content = ''

        title = root.find('.//article-title')
        if title is not None:
            article_content += ''.join(title.itertext()) + '\n'

        abstract = root.find('.//abstract')
        if abstract is not None:
            article_content += ''.join(abstract.itertext())

        body = root.find('.//body')
        if body is not None:
            sections = body.findall('.//sec')
            for section in sections:
                section = remove_figures_and_tables(section)

                sec_title = section.find('title')
                sec_content = ''.join(section.itertext())
                if sec_title is not None:
                    sec_title = ''.join(sec_title.itertext())
                    if (
                        'author contributions' in sec_title.lower() or
                        'interest' in sec_title.lower() or
                        'acknowledge' in sec_title.lower() or
                        'supplementary' in sec_title.lower()
                    ):
                        break
                    article_content += sec_content
        return article_content

    except Exception as e:
        print(f'Error occured for pmcID {pmcID}: {e}')


api_key = '54c9e70cfc18d3aaaf80821d83e4f2f7b509'
# print(api_key)
Entrez.api_key = api_key
Entrez.email = 'yc200@rice.edu'

with open('data/pmcids.json', 'r') as f:
    id_list = json.load(f)

sub_id_list = random.sample(id_list, 9999)
articles = []

for id in tqdm(sub_id_list):
    main_content = extract_main_content(id)
    if main_content is not None:
        article_dict = {'pmcID': id, 'main_content': main_content}
        articles.append(article_dict)
        id_list.remove(id)

with open('data/full_text/9.json', 'w') as f:
    json.dump(articles, f)

with open('data/pmcids.json', 'w') as f:
    json.dump(id_list, f)
# pdb.set_trace()