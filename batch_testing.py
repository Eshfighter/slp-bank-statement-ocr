import requests
import os
import json
import argparse
import time
import base64
import pandas as pd

transaction_fields = ['transactionDate', 'transactionDescriptions', 'transactionAmount', 'transactionType',
                      'transactionBalance', 'inDebt', 'transactionError']


def main(input_dir, bank_name, url):
    # Update url
    url = url.strip('/')
    url += '/pdf'

    abs_input_dir = os.path.abspath(input_dir)
    print('total files to process:', len(os.listdir(abs_input_dir)))

    # Log processing duration
    start = time.time()

    for file in sorted(os.listdir(abs_input_dir)):
        # Sanity check
        if not file.lower().endswith('pdf'):
            continue
        process(abs_input_dir, file, bank_name, url)

    end = time.time()
    print('processing duration:', end - start)


def process(input_dir, file, bank_name, url):
    print('processing:', file)

    # Read pdf and encode to b64 string
    with open(os.path.join(input_dir, file), 'rb') as pdf_file:
        b64_pdf = base64.b64encode(pdf_file.read()).decode()

        mediatype_json = 'application/json; charset=UTF-8'
        headers = {'Content-Type': mediatype_json,
                   'Accept': 'application/json'}
        data = {'bankName': bank_name,
                'fileContent': b64_pdf}
        response = requests.post(url, json=data, headers=headers)

        # Save results for debug purposes
        if response.status_code == 200:
            save(response.json(), file, input_dir)
        else:
            print(response.text)
            print('Error: Response code %d' % response.status_code)


def save(output_dict, filename, output_dir):
    if len(output_dict) == 0:
        return

    prefix = filename.split('.')[0]

    results_dir = os.path.join(output_dir, 'results')
    if not os.path.exists(results_dir):
        os.mkdir(results_dir)

    summary_list = []
    transactions_list = []

    for result in output_dict['statementResults']:
        summary_list.append(result['summary'])
        transactions_list.extend(result['transactions'])

    # Save summary as json
    with open(os.path.join(results_dir, '%s_summary.json' % prefix), 'w', encoding='utf-8') as summary_json:
        summary_json.write(json.dumps(summary_list, ensure_ascii=False))

    # Save transactions into csv file
    df = pd.DataFrame(transactions_list, columns=transaction_fields)

    if df is not None and df.size > 0:
        df.to_csv(os.path.join(results_dir, '%s_transactions.csv' % prefix))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input_dir", required=True, help="path to input directory")
    ap.add_argument("-b", "--bank_name", required=True, help="bank name")
    ap.add_argument("-u", "--url", required=True, help="url to server that will handle the bsocr requests")
    args = vars(ap.parse_args())

    main(args['input_dir'], args['bank_name'], args['url'])
