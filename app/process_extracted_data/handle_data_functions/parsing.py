# -*- coding: utf-8 -*-

import math

from .process import *
from app.utils import utils


def bank_alt_name_find(bank_name_find, bank_name, val_list_img):
    bank_alt_name = ''
    for line in val_list_img:
        line_array = line.split('  ')
        for txt in line_array:
            for bank in bank_name_find:
                if bank in txt and bank_alt_name == '':
                    bank_alt_name = bank_name
                    break
    return bank_alt_name


def bank_address_find(summary_config, val_list_img):
    bank_address_reference_text = summary_config['bank-add-find']
    address_start_line = summary_config['address-start-line']
    no_of_addr_line = summary_config['no-of-addr-lines']
    bank_add = ''
    for i, txt in enumerate(val_list_img):
        for bank in bank_address_reference_text:
            if bank in txt:
                bank_add = ''
                for x in range(int(address_start_line), int(no_of_addr_line+1)):
                    bank_add = ', '.join([bank_add, val_list_img[i+x].strip()])
                break
    if bank_add != '':
        bank_add = bank_add[1:].strip()

    return bank_add


def bank_info_find(configuration_fields, val_list_img):
    state_dt = ''
    acct_type = ''
    page_list = []
    extracted_account_number = ''
    page_keyword = configuration_fields["summary-config"]["page-keyword"]
    account_list = configuration_fields["summary-config"]["account-list"]
    state_dt_keyword = configuration_fields["summary-config"]["state-dt-keyword"] if 'state-dt-keyword' in configuration_fields['summary-config'] else None
    no_of_date_words = configuration_fields["summary-config"]["no-of-date-words"] if 'no-of-date-words' in configuration_fields['summary-config'] else None
    state_dt_regex = configuration_fields['summary-config']['state-dt-regex'] if 'state-dt-regex' in configuration_fields['summary-config'] else None

    for word in val_list_img:
        if page_keyword in word:
            word1 = word.split(' ')
            page_list.append(word1[-1])

        if state_dt_keyword:
            if state_dt_keyword in word:
                state_dt = word

                if 'state-dt-from-start' in configuration_fields['summary-config'] and configuration_fields['summary-config']['state-dt-from-start'] is True:
                    state_dt = state_dt.split(state_dt_keyword)[1].strip()
                    state_dt = state_dt.split(' ')
                    state_dt = ' '.join(state_dt[:no_of_date_words])
                elif state_dt_regex:
                    # Look for regex after keyword if applicable
                    state_dt_match = re.findall(state_dt_regex, word)
                    if len(state_dt_match) > 0:
                        state_dt = state_dt_match[len(state_dt_match) - 1]
                else:
                    state_dt = state_dt.split(' ')
                    state_dt = ' '.join(state_dt[-no_of_date_words:])

                if 'state-dt-separator' in configuration_fields['summary-config']:
                    state_dt_split = state_dt.split(configuration_fields['summary-config']['state-dt-separator'])
                    if len(state_dt_split) > 1:
                        if 'state-dt-from-start' in configuration_fields['summary-config'] and \
                                configuration_fields['summary-config']['state-dt-from-start'] is True:
                            state_dt = state_dt_split[0]
                        else:
                            state_dt = state_dt_split[1]
        elif state_dt_regex:
            # If keyword not present, look for regex
            state_dt_match = re.findall(state_dt_regex, word)
            if len(state_dt_match) > 0:
                state_dt = state_dt_match[len(state_dt_match) - 1]

        if acct_type == '':
            line_list = word.split('  ')
            acct_type = bank_acct_type_find(line_list, account_list)

        if 'account-no-regex' in configuration_fields["summary-config"]:
            # Use account number keyword as basis if exists, else look for regex without consideration
            if 'account-no-keyword' in configuration_fields['summary-config'] and len(configuration_fields['summary-config']['account-no-keyword']) > 0:
                if configuration_fields['summary-config']['account-no-keyword'] not in word:
                    continue

            regex = configuration_fields["summary-config"]['account-no-regex']
            regex_matched_text = re.findall(regex, word)
            if len(regex_matched_text) > 0:
                extracted_account_number = regex_matched_text[0]

    return page_list, state_dt, acct_type, extracted_account_number


def bank_acct_type_find(line_list, account_list):
    acct_type = ''
    for account in account_list:
        for text in line_list:
            if account in text:
                account_split = account.split(' ')
                text_split = text.split(' ')
                for word in text_split:
                    acct_type = acct_type + ' ' + word
                    acct_type = acct_type.strip()
                    if account_split[len(account_split) - 1].lower() in word.lower():
                        return acct_type
            elif text in account:
                return account

    return acct_type


def txn_find(bank_name,
             txn_key_word,
             txn_stop_at,
             date_regex_list,
             number_regex_list,
             txn_in_money,
             date_joined,
             balance_key_word,
             configuration_fields,
             text_list,
             extracted_table,
             last_page_last_txn,
             file_list=[],
             txn_amount_coordinate_list=[],
             txn_balance_coordinate_list=[],
             position_list=[],
             page_number_list=[]):
    txns = []
    key_word_no_add_desc = []
    update_lplt = False
    stop = False
    balance_in_separate_table = configuration_fields["transaction-config"]["balance-in-separate-table"]
    extra_index = configuration_fields["transaction-config"]["columns-in-between-date-descriptions"]
    date_index = configuration_fields['transaction-config']['transaction-date-index'] if 'transaction-date-index' in configuration_fields['transaction-config'] else 0

    # combine key word array with balance outside table array
    key_word_no_add_desc.extend(txn_key_word)
    key_word_no_add_desc.extend(balance_key_word)
    # conditions for each line of text
    for i, text_item_initial in enumerate(text_list):
        if len(text_item_initial.strip()) == 0:
            continue
        try:
            # remove noise
            text_item = text_item_initial.strip()
            text_item = text_item.replace('|', ' ')
            text_item = text_item.replace(' = ', '  ').replace(' — ', '  ')
            text_item_split_spaces = text_item.split('  ')
            text_item_split_spaces = list(filter(None, text_item_split_spaces))

            # Extra layer for number parsing in case of failed split
            text_item_split_numbers = []
            for item_element in text_item_split_spaces:
                item_element_numbers = re.findall(number_regex_list[0], item_element)
                item_element_split_space = item_element.strip().split(' ')
                if len(item_element_numbers) > 1 and len(item_element_numbers) == len(item_element_split_space):
                    added_count = 0
                    for j, number_item in enumerate(item_element_numbers):
                        # Handle negative number
                        if item_element_split_space[j].startswith('-'):
                            if len(number_item[0]) + 1 == len(item_element_split_space[j]):
                                text_item_split_numbers.append('-' + number_item[0])
                                added_count += 1
                        else:
                            if len(number_item[0]) == len(item_element_split_space[j]):
                                text_item_split_numbers.append(number_item[0])
                                added_count += 1

                    if added_count == 0:
                        text_item_split_numbers.append(item_element)
                else:
                    text_item_split_numbers.append(item_element)

            # Extra layer for date parsing in case of failed split
            text_item_split_date = []
            for item_element in text_item_split_numbers:
                item_element_dates = re.findall(date_regex_list[0], item_element)
                item_element_split_space = item_element.strip().split(' ')
                if len(item_element_dates) > 1 and len(item_element_dates) == len(item_element_split_space):
                    added_count = 0
                    for j, date_item in enumerate(item_element_dates):
                        if len(date_item) == len(item_element_split_space[j]):
                            text_item_split_date.append(date_item)
                            added_count += 1

                    if added_count == 0:
                        text_item_split_date.append(item_element)
                else:
                    text_item_split_date.append(item_element)

            text_item_processed_final = []
            for text in text_item_split_date:
                text = text.strip()
                if '%' in text:
                    if len(text) > 4:
                        text_item_processed_final.append(text)
                elif not re.search(r'[a-zA-Z0-9]', text):
                    continue
                else:
                    text_item_processed_final.append(text)
            balance_fields = configuration_fields["transaction-config"]["balance-fields"]
            if balance_in_separate_table:
                for balance_field in balance_fields['key']:
                    if (len(balance_fields['key']) != len(balance_fields['actual-key']) and balance_field.lower() in str(text_item_processed_final).lower()) or \
                       (len(balance_fields['key']) == len(balance_fields['actual-key']) and balance_field in text_item_processed_final):
                        row_with_balance_value = text_list[i+balance_fields['row-after-key']]
                        number_match = utils.regex_lookup(number_regex_list, row_with_balance_value)
                        if not number_match:
                            row_with_balance_value = text_list[i+balance_fields['row-after-key']+1]
                        row_with_balance_value = row_with_balance_value.replace('|', '').replace(' 7 ', '')
                        row_with_balance_value = re.sub(r'\s\s+', '_', str(row_with_balance_value))
                        row_with_balance_value = row_with_balance_value.split('_')

                        # Fix number regex if applicable
                        fixed_row_with_balance_value = []
                        for row_element in row_with_balance_value:
                            row_element_numbers = re.findall(number_regex_list[0], row_element)
                            if len(row_element_numbers) > 1:
                                for number_item in row_element_numbers:
                                    fixed_row_with_balance_value.append(number_item[0])
                            else:
                                fixed_row_with_balance_value.append(row_element)

                        txns = extract_balance_different_table(txns, balance_fields, number_regex_list, fixed_row_with_balance_value, position_list[i], file_name, page_number_list[i], txn_in_money)
                        break
            if not stop:
                extracted_transaction_row = []
                if date_joined and len(text_item_processed_final) > 0 and len(re.findall(number_regex_list[0], text_item_processed_final[-1].strip())) == 1:
                    process_transaction_text = []
                    for index, elem in enumerate(text_item_processed_final):
                        if index == 0:
                            for match in date_regex_list:
                                regex = '('+match+')'
                                process_transaction_text = re.split(regex, elem)
                                process_transaction_text = [text for text in process_transaction_text if bool(re.search(r'[a-z0-9]', text, re.IGNORECASE))]

                                # Make sure date is detected as first item
                                if len(re.findall(regex, elem)) > 0:
                                    if process_transaction_text.index(re.findall(regex, elem)[0]) == 0:
                                        break
                                    else:
                                        process_transaction_text = [elem]
                            extracted_transaction_row.extend(process_transaction_text)
                        else:
                            extracted_transaction_row.append(elem)
                else:
                    extracted_transaction_row = text_item_processed_final

                # if applicable, match with line from table extraction
                matched_table_line = None

                # Match extracted transaction row with applicable line extracted from table
                if extracted_table is not None:
                    extracted_transaction_row_joined = ''
                    for elem in extracted_transaction_row:
                        # Remove special characters
                        elem = elem.replace('/', '').replace('-', '')
                        elem_split = elem.split(' ')
                        for sub_elem in elem_split:
                            matched_whitespace = re.findall(' ', sub_elem)
                            if len(matched_whitespace) == len(sub_elem):
                                continue

                            extracted_transaction_row_joined += sub_elem.strip()
                            extracted_transaction_row_joined += ' '

                    extracted_transaction_row_joined = extracted_transaction_row_joined.strip()

                    for extracted_table_line in extracted_table:
                        extracted_table_line_joined = ''

                        # Remove special characters
                        for elem in extracted_table_line:
                            elem = elem.replace('/', '').replace('-', '')

                            elem_split = elem.split(' ')
                            for sub_elem in elem_split:
                                matched_whitespace = re.findall(' ', sub_elem)
                                if len(matched_whitespace) == len(sub_elem):
                                    continue

                                extracted_table_line_joined += sub_elem.strip()
                                extracted_table_line_joined += ' '

                        if extracted_transaction_row_joined == extracted_table_line_joined.strip():
                            matched_table_line = extracted_table_line
                            break

                # check if length of word is greater than 2 to remove noise
                temp_txn_row = []
                for transaction in extracted_transaction_row:
                    if transaction.islower():
                        if len(transaction) > 2:
                            temp_txn_row.append(transaction)
                    elif transaction.isdigit():
                        if len(transaction) >= 1:
                            temp_txn_row.append(transaction)
                    else:
                        if len(transaction) >= 2:
                            temp_txn_row.append(transaction)

                extracted_transaction_row = temp_txn_row
                for item_check in txn_stop_at:
                    for transaction_text in extracted_transaction_row:
                        if item_check.lower() in transaction_text.lower():
                            stop = True
                            break

                # Check if stop at regex exists, and if it does, stop
                if 'stop-at-regex' in configuration_fields['transaction-config']:
                    for transaction_text in extracted_transaction_row:
                        if len(re.findall(configuration_fields['transaction-config']['stop-at-regex'], transaction_text)) > 0:
                            stop = True
                            break

                if len(file_list) > 1:
                    file_name = file_list[i]
                else:
                    file_name = ''
                if len(txn_amount_coordinate_list) > 0:
                    txn_amount_coordinate = txn_amount_coordinate_list[i]
                else:
                    txn_amount_coordinate = []
                if len(txn_balance_coordinate_list) > 0:
                    txn_balance_coordinate = txn_balance_coordinate_list[i]
                else:
                    txn_balance_coordinate = []
                txns, keyword_detected = balance_extract(configuration_fields,
                                                         txn_key_word,
                                                         txns,
                                                         extracted_transaction_row,
                                                         txn_in_money,
                                                         date_regex_list,
                                                         file_name,
                                                         txn_amount_coordinate,
                                                         txn_balance_coordinate,
                                                         position_list[i],
                                                         page_number_list[i])
                if not stop and not keyword_detected:
                    # Disable lplt update if past first transaction of page
                    if update_lplt:
                        if 'page-first-transaction-index' in configuration_fields['transaction-config']:
                            if len(txns) > configuration_fields['transaction-config']['page-first-transaction-index']:
                                update_lplt = False
                            else:
                                if configuration_fields['transaction-config']['page-first-transaction-index'] > 0:
                                    # Make sure this is the beginning of a valid transaction page
                                    if len(txns) == 0 or len(txns) > 0 and 'transaction-description-1' in txns[0] \
                                       and txns[0]['transaction-description-1'] not in txn_key_word:
                                        update_lplt = False
                        else:
                            # Disable for non applicable statement templates
                            update_lplt = False

                    txns, lplt_updated = transaction_extract(configuration_fields,
                                                             bank_name,
                                                             txns,
                                                             last_page_last_txn if update_lplt else None,
                                                             extracted_transaction_row,
                                                             matched_table_line,
                                                             date_regex_list,
                                                             number_regex_list,
                                                             txn_in_money,
                                                             file_name,
                                                             txn_amount_coordinate,
                                                             txn_balance_coordinate,
                                                             balance_key_word,
                                                             balance_in_separate_table,
                                                             balance_fields,
                                                             position_list[i],
                                                             page_number_list[i],
                                                             date_index,
                                                             extra_index,
                                                             key_word_no_add_desc)

                    # Check if last page last txn needs to be updated
                    if len(txns) == 0 and 'last-column-headings' in configuration_fields['transaction-config']:
                        last_column_headings = configuration_fields['transaction-config']['last-column-headings']
                        lch_match_count = 0
                        for extracted_item in extracted_transaction_row:
                            if extracted_item.strip() in last_column_headings:
                                lch_match_count += 1
                        if lch_match_count >= 3:
                            update_lplt = True

                    if lplt_updated:
                        last_page_last_txn = lplt_updated

                    if 'requires-balance-calculation' in configuration_fields['transaction-config'] and \
                            configuration_fields['transaction-config']['requires-balance-calculation'] is True and\
                            len(txns) > 0:
                        current_txn = txns[-1]
                        last_txn = txns[-2] if len(txns) > 1 else last_page_last_txn

                        if current_txn and last_txn and \
                                current_txn['transaction-balance'] is None and last_txn['transaction-balance'] is not None:
                            last_txn_balance = last_txn['transaction-balance']
                            if last_txn['in-debt']:
                                last_txn_balance *= -1

                            if current_txn['transaction-type'] == 'Debit':
                                # Debit
                                current_txn_balance = float('%.02f' % round(last_txn_balance - current_txn['transaction-amount'], 2))
                            else:
                                # Credit
                                current_txn_balance = float('%.02f' % round(last_txn_balance + current_txn['transaction-amount'], 2))

                            # Handle in-debt status
                            current_txn['transaction-balance'] = abs(current_txn_balance)
                            if current_txn_balance < 0:
                                current_txn['in-debt'] = True
                            else:
                                current_txn['in-debt'] = False
        except:
            pass

    return txns, last_page_last_txn


def extract_balance_different_table(txns, balance_fields, number_regex_list, text_input, position_item, file_name, page_number, txn_in_money):
    mdata = {}
    mdata['file-name'] = file_name

    balance_values = []
    for text in text_input:
        number_match = utils.regex_lookup(number_regex_list, text)
        if number_match:
            balance_values.append(text)

    # Check if balance is split horizontally and adjust array accordingly
    if 'actual-key-horizontal-split' in balance_fields:
        actual_keys = []
        for split_indices in balance_fields['actual-key-horizontal-split']:
            if len(split_indices) == len(balance_values):
                for index in split_indices:
                    actual_keys.append(balance_fields['actual-key'][index])

    else:
        actual_keys = balance_fields['actual-key']

    # Process if length of arrays are the same
    if len(actual_keys) == len(balance_values):
        for i, balance_field in enumerate(actual_keys):
            mdata["transaction-description-1"] = balance_field
            balance, cd1, num2, num3, in_debt = convertStrToMoneyImg(balance_values[i], txn_in_money)
            mdata["transaction-balance"] = balance
            mdata["in-debt"] = in_debt
            mdata["transaction-date"] = None
            mdata["transaction-amount"] = None
            mdata["transaction-type"] = None
            mdata["top-distance"] = position_item['top']
            mdata["page"] = page_number
            mdata["height"] = position_item['height']
            txns.append(mdata)
            mdata = {}
    else:
        for i, balance_field in enumerate(balance_fields['actual-key']):
            for text in text_input:
                if balance_field in text:
                    mdata["transaction-description-1"] = balance_field
                    balance, cd1, num2, num3, in_debt = convertStrToMoneyImg(balance_values[0], txn_in_money)
                    mdata["transaction-balance"] = balance
                    mdata["in-debt"] = in_debt
                    mdata["transaction-date"] = None
                    mdata["transaction-amount"] = None
                    mdata["transaction-type"] = None
                    mdata["top-distance"] = position_item['top']
                    mdata["page"] = page_number
                    mdata["height"] = position_item['height']
                    txns.append(mdata)
                    mdata = {}

    return txns


def balance_extract(configuration_fields, txn_key_word, txns, input_item, txn_in_money, date_regex_list, file_name, txn_amount_coordinate, txn_balance_coordinate, position_item, page_number):
    keyword_detected = False
    mdata = {}
    date_match = utils.regex_lookup(date_regex_list, input_item)
    transaction_date_format = configuration_fields['transaction-config']['transaction-date-format']
    for item_key in txn_key_word:
        for i, extracted_text in enumerate(input_item):
            if item_key in extracted_text:
                if date_match:
                    for reg in date_regex_list:
                        regex = '(' + reg + ')'
                        regex_compile = re.compile(regex)
                        date_item = [j for j in input_item if regex_compile.match(j)]
                        if len(date_item) > 0:
                            parsed_date = convert_date_to_DDMM(date_item[0], transaction_date_format)
                            if len(parsed_date) > 0:
                                mdata["transaction-date"] = parsed_date
                            else:
                                mdata["transaction-date"] = None
                        else:
                            mdata["transaction-date"] = None
                else:
                    mdata["transaction-date"] = None
                mdata["transaction-description-1"] = item_key
                try:
                    balance, cd1, num2, num3, in_debt = convertStrToMoneyImg(input_item[-1], txn_in_money)
                except:
                    balance = float('NaN')
                    in_debt = None
                mdata["transaction-type"] = None
                mdata["transaction-amount"] = None
                if balance is None or math.isnan(balance):
                    mdata["transaction-balance"] = None
                else:
                    mdata["transaction-balance"] = balance
                keyword_detected = True
                mdata['file-name'] = file_name
                mdata['txn-amt-coordinate'] = txn_amount_coordinate
                mdata['txn-balance-coordinate'] = txn_balance_coordinate
                mdata["in-debt"] = in_debt
                mdata["top-distance"] = position_item['top']
                mdata["page"] = page_number
                mdata["height"] = position_item['height']
                txns.append(mdata)
            else:
                continue

    return txns, keyword_detected


def transaction_extract(configuration_fields,
                        bank_name,
                        txns,
                        last_page_last_txn,
                        input_item,
                        input_item_from_table,
                        date_regex_list,
                        number_regex_list,
                        txn_in_money,
                        file_name,
                        txn_amount_coordinate,
                        txn_balance_coordinate,
                        balance_key_word,
                        balance_in_separate_table,
                        balance_fields,
                        position_item,
                        page_number,
                        date_index,
                        extra_index,
                        key_word_no_add_desc):
    mdata = {}
    date_match = False
    number_match = False
    month_match = False
    add_txn = True
    transaction_date_format = configuration_fields['transaction-config']['transaction-date-format']

    for key_word in balance_key_word:
        if len(txns) > 0:
            if txns[len(txns)-1]["transaction-description-1"] is not None and key_word in txns[len(txns)-1]["transaction-description-1"]:
                add_txn = False
                break

    if input_item_from_table:
        # Table parsing implementation
        required_column_indices = configuration_fields['transaction-config']['required-txn-columns']
        transaction_columns = configuration_fields['transaction-config']['txn-columns']
        last_txn = None

        # Date
        txn_date_index = transaction_columns.index('transaction-date')
        if txn_date_index in required_column_indices and len(input_item_from_table[txn_date_index]) > 0:
            # Date present, check regex
            has_whitespace = False
            for date_regex in date_regex_list:
                if r'\s' in date_regex:
                    has_whitespace = True
                    break

            if has_whitespace:
                date_match = utils.regex_lookup(date_regex_list, input_item_from_table[txn_date_index])
            else:
                date_match = utils.regex_lookup(date_regex_list, input_item_from_table[txn_date_index].replace(' ', ''))

            if date_match:
                mdata["transaction-date"] = convert_date_to_DDMM(input_item_from_table[txn_date_index], transaction_date_format)
            else:
                return txns, last_page_last_txn
        else:
            if len(txns) > 0:
                last_txn = txns[-1]

        # Description
        txn_description_indices = [transaction_columns.index(key) for key in transaction_columns if 'transaction-description' in key]
        if len(txn_description_indices) == 1:
            if txn_description_indices[0] in required_column_indices:
                # Single description field
                if last_txn:
                    txn_description_index = 1
                    while True:
                        txn_description_key = 'transaction-description-' + str(txn_description_index)
                        if txn_description_key in last_txn:
                            txn_description_index += 1
                        else:
                            last_txn[txn_description_key] = input_item_from_table[txn_description_indices[0]]
                            break
                else:
                    # Handle cases where cheque number required
                    if 'txn-description-include-additional-column' in configuration_fields['transaction-config'] and \
                            configuration_fields['transaction-config'][
                                'txn-description-include-additional-column'] is True:
                        desc_string = input_item_from_table[txn_description_indices[0]]
                        desc_string_split = desc_string.split(' ')
                        if desc_string_split[-1].strip().isdigit():
                            # Cheque number found, put this first
                            mdata['transaction-description-1'] = desc_string_split[-1].strip()
                            mdata['transaction-description-2'] = desc_string.split(mdata['transaction-description-1'])[0].strip()
                        else:
                            mdata['transaction-description-1'] = input_item_from_table[txn_description_indices[0]]
                    else:
                        mdata['transaction-description-1'] = input_item_from_table[txn_description_indices[0]]
        else:
            for txn_description_index in txn_description_indices:
                if txn_description_index in required_column_indices:
                    txn_description_key = transaction_columns[txn_description_index]
                    if len(input_item_from_table[txn_description_index]) > 0:
                        if last_txn:
                            if txn_description_key in last_txn:
                                last_txn[txn_description_key] += (' ' + input_item_from_table[txn_description_index])
                            else:
                                last_txn[txn_description_key] = input_item_from_table[txn_description_index]
                        else:
                            mdata[txn_description_key] = input_item_from_table[txn_description_index]

        # Amounts
        if not last_txn:
            # Credit
            txn_credit_index = transaction_columns.index('transaction-credit')
            has_amount = False
            if txn_credit_index in required_column_indices and len(input_item_from_table[txn_credit_index]) > 1:
                amount, cd, num, num1, in_debt = convertStrToMoneyImg(input_item_from_table[txn_credit_index], txn_in_money)
                mdata['transaction-amount'] = amount
                mdata['transaction-type'] = 'Credit'
                has_amount = True

            txn_debit_index = transaction_columns.index('transaction-debit')
            if txn_credit_index in required_column_indices and len(input_item_from_table[txn_debit_index]) > 1:
                amount, cd, num, num1, in_debt = convertStrToMoneyImg(input_item_from_table[txn_debit_index], txn_in_money)
                mdata['transaction-amount'] = amount
                mdata['transaction-type'] = 'Debit'
                has_amount = True

            if not has_amount:
                mdata['transaction-amount'] = 0
                mdata['transaction-type'] = None

            txn_balance_index = transaction_columns.index('transaction-balance')
            if txn_credit_index in required_column_indices and len(input_item_from_table[txn_balance_index]) > 0:
                balance, cd, num, num1, in_debt = convertStrToMoneyImg(input_item_from_table[txn_balance_index], txn_in_money)
                mdata['transaction-balance'] = balance
                mdata['in-debt'] = in_debt
            else:
                mdata['transaction-balance'] = None
                mdata['in-debt'] = None

            # Add to txns
            mdata['file-name'] = file_name
            mdata['txn-amt-coordinate'] = txn_amount_coordinate
            mdata['txn-balance-coordinate'] = txn_balance_coordinate
            mdata["top-distance"] = position_item['top']
            mdata["page"] = page_number
            mdata["height"] = position_item['height']
            txns.append(mdata)
    else:
        # Text parsing implementation
        if date_index > len(input_item) - 1:
            date_index = 0

        if len(input_item) > 0:
            has_whitespace = False
            for date_regex in date_regex_list:
                if r'\s' in date_regex:
                    has_whitespace = True
                    break

            if has_whitespace:
                date_match = utils.regex_lookup(date_regex_list, input_item[date_index])
            else:
                date_match = utils.regex_lookup(date_regex_list, input_item[date_index].replace(' ', ''))

            if bank_name != 'Maybank' and bank_name != 'UOB' and bank_name != 'RHB':
                number_match = utils.regex_lookup(number_regex_list, input_item)
            month_match = utils.find_month_text(input_item[date_index])

        # Skip if account name is in description
        for account_name in configuration_fields['summary-config']['account-list']:
            if account_name in input_item:
                return txns, last_page_last_txn

        if len(input_item) >= 4 and utils.regex_lookup(number_regex_list, [input_item[-1]]):
            # this case is for transaction amount
            if date_match or number_match or month_match:
                if date_match or month_match:
                    mdata["transaction-date"] = convert_date_to_DDMM(input_item[date_index].strip(), transaction_date_format)
                    if 'txn-description-include-additional-column' in configuration_fields['transaction-config'] and \
                            configuration_fields['transaction-config']['txn-description-include-additional-column'] is True:
                        if 2 + extra_index < len(input_item) and input_item[2+extra_index].strip().isdigit():
                            mdata['transaction-description-1'] = input_item[2+extra_index].strip()

                    initial_description_index = 1
                else:
                    if len(txns) > 0:
                        mdata["transaction-date"] = txns[-1]['transaction-date']
                    else:
                        mdata["transaction-date"] = None

                    initial_description_index = 0

                if 'transaction-description-1' in mdata:
                    mdata["transaction-description-2"] = input_item[initial_description_index+extra_index]
                else:
                    mdata["transaction-description-1"] = input_item[initial_description_index+extra_index]

                # Handling formatting quirks
                if input_item[-2].strip().isdigit():
                    amount = None
                    balance = None
                    # TODO: Cleanup implementation
                    if configuration_fields['init-config']['format-id'] == 'rhb_my_2':
                        # RHB MY 2 - there are transactions that have no amount
                        amount = 0
                        balance, cd1, num2, num3, in_debt = convertStrToMoneyImg(input_item[-1], txn_in_money)
                        mdata["transaction-type"] = cd1
                        mdata["in-debt"] = in_debt
                else:
                    amount, cd, num, num1, in_debt = convertStrToMoneyImg(input_item[-2], txn_in_money)

                    # Handle UOB my 2 where zero values are stated every transaction line
                    if configuration_fields['init-config']['format-id'] == 'uob_my_2' and math.isclose(amount, 0):
                        amount, cd, num, num1, in_debt = convertStrToMoneyImg(input_item[-3], txn_in_money)

                    balance, cd1, num2, num3, in_debt = convertStrToMoneyImg(input_item[-1], txn_in_money)
                    mdata["transaction-type"] = cd
                    mdata["in-debt"] = in_debt
                if amount is None or math.isnan(amount):
                    amount, cd, num, num1, in_debt = convertStrToMoneyImg(input_item[-3], txn_in_money)
                    if amount is None or math.isnan(amount):
                        mdata["transaction-amount"] = None
                    else:
                        mdata["transaction-amount"] = amount
                else:
                    mdata["transaction-amount"] = amount
                if balance is None or math.isnan(balance):
                    mdata["transaction-balance"] = None
                else:
                    mdata["transaction-balance"] = balance
                mdata['file-name'] = file_name
                mdata['txn-amt-coordinate'] = txn_amount_coordinate
                mdata['txn-balance-coordinate'] = txn_balance_coordinate
                mdata["top-distance"] = position_item['top']
                mdata["page"] = page_number
                mdata["height"] = position_item['height']
                txns.append(mdata)
        elif number_match and len(input_item) > 1 and len(input_item[0+extra_index].split(' ')) < 15:
            if add_txn:
                try:
                    transaction_numbers = []
                    in_debt = False
                    for field in input_item:
                        field = field.lstrip('-')
                        field = field.replace(' ', '')
                        extracted_numbers = re.findall(r'([0-9]{1,3}(,[0-9]{3})*(\.|\,)[0-9]{2})', field)
                        if len(extracted_numbers) > 0:
                            extracted_number = extracted_numbers[0][0]
                            extracted_number = process_money_value(extracted_number)
                            if 'DR' in field or 'OD' in field:
                                in_debt = True
                            transaction_numbers.append(extracted_number)
                    if len(transaction_numbers) > 0:
                        try:
                            mdata["transaction-amount"] = convertStrToMoneyImg(transaction_numbers[0], txn_in_money)[0]
                        except:
                            mdata["transaction-amount"] = None
                        try:
                            mdata["transaction-balance"] = convertStrToMoneyImg(transaction_numbers[1], txn_in_money)[0]
                        except:
                            mdata["transaction-balance"] = None
                    if not date_match:
                        if not transaction_numbers[0] in input_item[0+extra_index]:
                            mdata["transaction-description-1"] = input_item[0+extra_index]
                        else:
                            mdata["transaction-description-1"] = None
                        mdata["transaction-date"] = txns[-1]['transaction-date'] if len(txns) > 0 else None
                        mdata["transaction-type"] = None
                        mdata['file-name'] = file_name
                        mdata['txn-amt-coordinate'] = txn_amount_coordinate
                        mdata['txn-balance-coordinate'] = txn_balance_coordinate
                        mdata["in-debt"] = in_debt
                        mdata["top-distance"] = position_item['top']
                        mdata["page"] = page_number
                        mdata["height"] = position_item['height']
                        txns.append(mdata)
                    else:
                        if not transaction_numbers[0] in input_item[1+extra_index]:
                            mdata["transaction-description-1"] = input_item[1+extra_index]
                        else:
                            mdata["transaction-description-1"] = None
                        mdata["transaction-date"] = convert_date_to_DDMM(input_item[date_index], transaction_date_format)
                        mdata["transaction-type"] = None
                        mdata['file-name'] = file_name
                        mdata['txn-amt-coordinate'] = txn_amount_coordinate
                        mdata['txn-balance-coordinate'] = txn_balance_coordinate
                        mdata["in-debt"] = in_debt
                        mdata["top-distance"] = position_item['top']
                        mdata["page"] = page_number
                        mdata["height"] = position_item['height']
                        txns.append(mdata)
                except:
                    pass
        elif len(input_item) > 0:
            # this case is for additional transaction details
            add_additional_desc = True

            # Handle lplt
            if last_page_last_txn:
                for key_word in key_word_no_add_desc:
                    if last_page_last_txn["transaction-description-1"] is not None and key_word in last_page_last_txn["transaction-description-1"]:
                        add_additional_desc = False
                if balance_in_separate_table:
                    for balance_field in balance_fields['actual-key']:
                        if last_page_last_txn["transaction-description-1"] is not None and balance_field in last_page_last_txn["transaction-description-1"]:
                            add_additional_desc = False
                if add_additional_desc and len(input_item[0].split(' ')) < 15:
                    no_of_items = len(last_page_last_txn.keys())
                    descrStr = "transaction-description-" + str(no_of_items - 10)
                    description_text = input_item[0].strip()
                    last_page_last_txn[descrStr] = description_text

            if len(txns) > 0:
                for key_word in key_word_no_add_desc:
                    if txns[len(txns)-1]["transaction-description-1"] is not None and key_word in txns[len(txns)-1]["transaction-description-1"]:
                        add_additional_desc = False
                if balance_in_separate_table:
                    for balance_field in balance_fields['actual-key']:
                        if txns[len(txns)-1]["transaction-description-1"] is not None and balance_field in txns[len(txns)-1]["transaction-description-1"]:
                            add_additional_desc = False
                if add_additional_desc:
                    for item in input_item:
                        if len(item.split(' ')) < 15:
                            no_of_items = len(txns[len(txns) - 1].keys())
                            descrStr = "transaction-description-"+str(no_of_items-10)
                            description_text = item.strip()

                            # Check if part of description needs ignoring
                            if 'txn-description-ignore-regex' in configuration_fields['transaction-config']:
                                for txn_ignore_regex in configuration_fields['transaction-config']['txn-description-ignore-regex']:
                                    txn_ignore_match = re.findall(txn_ignore_regex, description_text)
                                    if txn_ignore_match:
                                        description_text = description_text.replace(txn_ignore_match[0], '').strip()

                            if len(description_text) > 0:
                                txns[len(txns)-1][descrStr] = description_text

    return txns, last_page_last_txn


def find_field_based_on_label(label_list, index, val_list_img, line=0):
    value = ''
    value_found = False
    for i, text in enumerate(val_list_img):
        if not value_found:
            for label in label_list:
                if label in text:
                    text_list = text.split(label)
                    value = text_list[index].strip()
                    if line > 0:
                        for j in range(line):
                            line_list = val_list_img[i+j+1].split('  ')
                            next_line_to_join = [line_text for line_text in line_list if len(line_text) > 1]
                            lines_to_join = list(filter(None, [value, next_line_to_join[0]]))
                            value = ', '.join(lines_to_join)
                    elif line < 0:
                        for j in range(abs(line)):
                            line_list = val_list_img[i-j-1].split('  ')
                            next_line_to_join = [line_text.strip() for line_text in line_list if len(line_text.strip()) > 1]
                            lines_to_join = list(filter(None, [value, next_line_to_join[0]]))
                            value = ', '.join(lines_to_join)
                    value_found = True
                    break

    return value


def find_transaction_summary_info(statement_data, configuration_fields):
    summary_data = statement_data['final-summary']
    transaction_data = statement_data['final-transaction']
    transaction_summary_key_info = configuration_fields['transaction-config']['transaction-summary-key-info']
    for key_info in transaction_summary_key_info:
        for transaction in transaction_data:
            for keyword in key_info['keyword']:
                if transaction['transaction-description-1'] is not None and keyword in transaction['transaction-description-1']:
                    if 'in-debt' in transaction and transaction['in-debt'] is True:
                        summary_data[key_info['key']] = -1 * transaction['transaction-balance']
                    else:
                        summary_data[key_info['key']] = transaction['transaction-balance']

    return summary_data
