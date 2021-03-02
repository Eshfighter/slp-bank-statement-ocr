#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from decimal import Decimal
import cv2
from app.extract_data import tesseract_ocr
import datetime

full_month_list = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']

def convertStrToMoneyImg(mystr, txn_type_available):
    cd = ""
    in_debt = False
    if mystr.strip().startswith('-') or mystr.strip().endswith('-') or 'DR' in mystr or 'OD' in mystr or (
        mystr.strip().startswith('(') and mystr.strip().endswith(')')):
        in_debt = True
    money_value = process_money_value(mystr)
    if txn_type_available:
        if '+' in money_value:
            cd = "Credit"
        elif '-' in money_value:
            cd = "Debit"
        elif '' in money_value:
            cd = None
    else:
        cd = None

    try:
        extracted_numbers = re.findall(r'([0-9]{1,3}((\.|\,)[0-9]{3})*(\.|\,)[0-9]{2})', money_value)
        extracted_number = extracted_numbers[0][0]
        s1 = extracted_number
    except:
        s1 = re.sub(r'[+-]', '', money_value)

    # Remove multiple instances of the . character if they exist
    if s1.count('.') > 1:
        # Remove all periods except the last period
        period_indices = []
        for i, character in enumerate(s1):
            if character == '.':
                period_indices.append(i)
        period_indices.pop()
        for period_index in period_indices:
            s1 = s1[:period_index] + s1[period_index + 1:]
    st = re.sub(r'[^\d\-.]', '', s1)

    if '.' not in st:
        st = st[:len(st)-2] + '.' + st[len(st)-2:]
    if len(st) > 0:
        try:
            balance = Decimal(st)
            balance = round(balance, 2)
            return float(balance), cd, s1, float(st), in_debt
        except:
            return None, cd, "blank", None, False
    else:
        return None, cd, "blank", None, False


def process_money_value(mystr):
    if ' 1' in mystr[-2:]:
        mystr = mystr.replace(' 1', '')
    if '1 ' in mystr[0:2]:
        mystr = mystr.replace('1 ', '')
    if ' |' in mystr[-2:]:
        mystr = mystr.replace(' |', '')
    if '| ' in mystr[0:2]:
        mystr = mystr.replace('| ', '')

    mystr = re.sub(r'[^.,\+\-0-9]', r'', mystr).strip()

    if " " in mystr:
        mystr = mystr.replace(' ', ',')
    if ',.' in mystr or '.,' in mystr:
        mystr = mystr.replace(',.', ',').replace('.,', ',')
    if mystr[0:1] == "-":
        mystr = mystr[0:1].replace('-', '.') + mystr[1:]
    if mystr[-4:-3] == "," and (mystr.endswith('+') or mystr.endswith('-')):
        string_length = len(mystr)
        mystr = mystr[0:string_length-4] + '.' + mystr[string_length-3:]
    if mystr[-3:-2] == ",":
        string_length = len(mystr)
        mystr = mystr[0:string_length-3] + '.' + mystr[string_length-2:]
    if not '.' in mystr:
        string_length = len(mystr)
        if mystr.endswith('+') or mystr.endswith('-'):
            mystr = mystr[0:string_length-3] + '.' + mystr[string_length-3:]
        else:
            mystr = mystr[0:string_length-2] + '.' + mystr[string_length-2:]
    try:
        mystr = "{:,.2f}".format(float(mystr))
    except:
        pass

    return mystr


def extract_transaction_type_and_error(transaction_list, configuration_fields):
    keyword_list = configuration_fields["transaction-config"]["txn-key-word"]
    balance_in_separate_table = configuration_fields["transaction-config"]["balance-in-separate-table"]

    # Reverse transactions if reverse chronological order
    adjusted_transaction_list = transaction_list
    txn_start_index = -1
    txn_end_index = -1
    if 'txn-reverse-chronological' in configuration_fields['transaction-config'] and configuration_fields['transaction-config']['txn-reverse-chronological'] is True:
        for i, txn in enumerate(transaction_list):
            if i > 0 and txn['transaction-date'] is not None and transaction_list[i-1]['transaction-date'] is None:
                if txn_start_index == -1:
                    txn_start_index = i
            elif i > 0 and txn['transaction-date'] is None and transaction_list[i-1]['transaction-date'] is not None:
                if txn_end_index == -1:
                    txn_end_index = i-1

        reversed_transaction_list = transaction_list[txn_start_index:txn_end_index+1]
        reversed_transaction_list.reverse()

        # Insert into adjusted transaction list
        adjusted_transaction_list[txn_start_index:txn_end_index+1] = reversed_transaction_list

    # Separate opening balance if applicable
    opening_balance_txn = None
    opening_balance_key_word = None

    transaction_summary_key_info = configuration_fields['transaction-config']['transaction-summary-key-info']
    for key_info in transaction_summary_key_info:
        if key_info['key'] == 'start-balance':
            opening_balance_key_word = key_info['keyword'][0]

    # Get first transaction line index
    first_txn_index = -1
    for i, txn in enumerate(adjusted_transaction_list):
        if i > 0 and txn['transaction-date'] is not None:
            first_txn_index = i
            break

    for i, transaction in enumerate(adjusted_transaction_list):
        identify_transaction_type = True
        for keyword in keyword_list:
            if transaction['transaction-description-1'] is not None and keyword in transaction['transaction-description-1']:
                identify_transaction_type = False
        if balance_in_separate_table:
            balance_fields = configuration_fields["transaction-config"]["balance-fields"]
            for balance_field in balance_fields['actual-key']:
                if transaction['transaction-description-1'] is not None and balance_field in transaction['transaction-description-1']:
                    identify_transaction_type = False

                # Check if opening balance
                if opening_balance_txn is None and opening_balance_key_word is not None and transaction['transaction-description-1'] == opening_balance_key_word:
                    opening_balance_txn = transaction

        if opening_balance_txn is not None and i == first_txn_index:
            last_transaction = opening_balance_txn
        else:
            last_transaction = transaction_list[i-1]
        if identify_transaction_type and i > 0 and last_transaction['transaction-balance'] is not None:
            try:
                if transaction['transaction-balance'] is None or transaction['transaction-amount'] is None:
                    transaction['transaction-error'] = True
                    continue
                transaction_balance = transaction['transaction-balance']
                prev_transaction_balance = last_transaction['transaction-balance']
                if transaction['in-debt'] and last_transaction['in-debt']:
                    if (float(prev_transaction_balance) - float(transaction_balance)) < 0:
                        transaction['transaction-type'] = 'Debit'
                    elif (float(prev_transaction_balance) - float(transaction_balance)) > 0:
                        transaction['transaction-type'] = 'Credit'
                elif transaction['in-debt'] and not last_transaction['in-debt']:
                    transaction['transaction-type'] = 'Debit'
                elif not transaction['in-debt'] and last_transaction['in-debt']:
                    transaction['transaction-type'] = 'Credit'
                else:
                    if (float(prev_transaction_balance) - float(transaction_balance)) > 0:
                        transaction['transaction-type'] = 'Debit'
                    elif (float(prev_transaction_balance) - float(transaction_balance)) < 0:
                        transaction['transaction-type'] = 'Credit'

                transaction_amount = transaction['transaction-amount']
                transaction_match_1 = (round(abs(float(transaction_balance) - float(prev_transaction_balance)), 2) == float(transaction_amount))
                transaction_match_2 = (round(abs(float(transaction_balance) + float(prev_transaction_balance)), 2) == float(transaction_amount))
                if transaction_match_1 or transaction_match_2:
                    transaction['transaction-error'] = False
                else:
                    transaction['transaction-error'] = True
            except:
                transaction['transaction-type'] = None
                transaction['transaction-error'] = False
        else:
            transaction['transaction-type'] = None
            transaction['transaction-error'] = False

    # Reverse back transaction list after processing
    if 'txn-reverse-chronological' in configuration_fields['transaction-config'] and configuration_fields['transaction-config']['txn-reverse-chronological'] is True:
        reversed_transaction_list = adjusted_transaction_list[txn_start_index:txn_end_index+1]
        reversed_transaction_list.reverse()

        # Insert into adjusted transaction list
        transaction_list[txn_start_index:txn_end_index+1] = reversed_transaction_list

    return transaction_list


def run_number_model(transaction_list, configuration_fields, segment):
    txn_in_money = configuration_fields["transaction-config"]["txn-type-in-money-value"]

    for i, transaction in enumerate(transaction_list):
        transaction_error = check_transaction_error(transaction, transaction_list[i-1])
        if transaction['transaction-error'] and transaction_error:
            try:
                file_img = cv2.imread(transaction['file-name'])
                if len(transaction['txn-amt-coordinate']) > 0:
                    # transaction amount through number model
                    txn_amount_img = file_img[transaction['txn-amt-coordinate'][0]:transaction['txn-amt-coordinate'][1], transaction['txn-amt-coordinate'][2]:transaction['txn-amt-coordinate'][3]]
                    result_amount = tesseract_ocr.convert_image_to_string_number(txn_amount_img, segment)
                    transaction_amount, cd, num2, num3, in_debt = convertStrToMoneyImg(result_amount, txn_in_money)
                    transaction['transaction-amount'] = transaction_amount
                    transaction["transaction-type"] = cd
                if len(transaction['txn-balance-coordinate']) > 0:
                    # balance through number model
                    txn_balance_img = file_img[transaction['txn-balance-coordinate'][0]:transaction['txn-balance-coordinate'][1], transaction['txn-balance-coordinate'][2]:transaction['txn-balance-coordinate'][3]]
                    result_balance = tesseract_ocr.convert_image_to_string_number(txn_balance_img, segment)
                    transaction_balance, cd, num2, num3, in_debt = convertStrToMoneyImg(result_balance, txn_in_money)
                    transaction['transaction-balance'] = transaction_balance
            except:
                pass
        if segment == 'line':
            try:
                del transaction['file-name']
            except:
                pass
            try:
                del transaction['txn-amt-coordinate']
            except:
                pass
            try:
                del transaction['txn-balance-coordinate']
            except:
                pass

    transaction_list = extract_transaction_type_and_error(transaction_list, configuration_fields)
    return transaction_list


def process_summary_list(final_statement_results):
    for i, result in enumerate(final_statement_results):
        for key in result['summary'][0]:
            if result['summary'][0][key] == '':
                for summary in result['summary']:
                    if summary[key] != '':
                        final_statement_results[i]['summary'][0][key] = summary[key]
                        break
        final_statement_results[i]['summary'] = final_statement_results[i]['summary'][0]

    return final_statement_results


def getMonth(month):
    month_list = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    try:
        month_index = month_list.index(month.upper()) + 1
        month_string = "{:02d}".format(month_index)
    except:
        month_string = '00'

    return month_string


def check_transaction_error(current_transaction, prev_transaction):
    if current_transaction['transaction-balance'] is None or current_transaction['transaction-amount'] is None or prev_transaction['transaction-balance'] is None:
        return False
    else:
        transaction_balance = current_transaction['transaction-balance']
        transaction_amount = current_transaction['transaction-amount']
        prev_transaction_balance = prev_transaction['transaction-balance']
        transaction_match_1 = (round(abs(float(transaction_balance) - float(prev_transaction_balance)), 2) == float(transaction_amount))
        transaction_match_2 = (round(abs(float(transaction_balance) + float(prev_transaction_balance)), 2) == float(transaction_amount))
        if transaction_match_1 or transaction_match_2:
            return False
        else:
            return True


def convert_descriptions_to_list(transactions_list):
    for i, transaction in enumerate(transactions_list):
        transaction['transaction-descriptions'] = []
        for key in list(transaction):
            if 'transaction-description-' in key:
                if transaction[key] is not None:
                    transaction['transaction-descriptions'].append(transaction[key].strip())
                del transaction[key]

    return transactions_list


def convert_date_to_DDMMYY(state_dt, date_format):
    if ' ' not in date_format:
        state_dt = state_dt.replace(' ', '')

    date_matched_string = None
    date_format_identifier = None
    if date_format == 'DD MMM YYYY':
        matched = re.findall('(\d\d\s[a-zA-Z][a-zA-Z][a-zA-Z]\s\d\d\d\d)', state_dt)
        if len(matched) > 0:
            date_matched_string = matched[0]
            date_format_identifier = "%d %b %Y"
    elif date_format == 'DD M YYYY':
        split_date = state_dt.split(' ')
        if len(split_date) == 3:
            match_day = len(re.findall('(\d\d)', split_date[0])) == 1
            match_year = len(re.findall('(\d\d\d\d)', split_date[2])) == 1
            match_month = split_date[1].lower() in full_month_list
            if match_day and match_year and match_month:
                date_matched_string = state_dt
                date_format_identifier = "%d %B %Y"
    elif date_format == 'DD/MM/YYYY':
        matched = re.findall(r'(\d\d/\d\d/\d\d\d\d)', state_dt)
        if len(matched) > 0:
            date_matched_string = matched[0]
            date_format_identifier = "%d/%m/%Y"
    elif date_format == 'DD/MM/YY':
        matched = re.findall(r'(\d\d/\d\d/\d\d)', state_dt)
        if len(matched) > 0:
            date_matched_string = matched[0]
            date_format_identifier = "%d/%m/%y"
    elif date_format == 'MMM DD, YYYY':
        matched = re.findall(r'([a-zA-Z][a-zA-Z][a-zA-Z]\s\d\d,\s\d\d\d\d)', state_dt)
        if len(matched) > 0:
            date_matched_string = matched[0]
            date_format_identifier = "%b %d, %Y"
    elif date_format == 'DD-MMM-YYYY':
        matched = re.findall(r'(\d\d-[a-zA-Z][a-zA-Z][a-zA-Z]-\d\d\d\d)', state_dt)
        if len(matched) > 0:
            date_matched_string = matched[0]
            date_format_identifier = "%d-%b-%Y"

    if date_matched_string and date_format_identifier:
        try:
            date_formatter = datetime.datetime.strptime(date_matched_string, date_format_identifier)
            return date_formatter.strftime('%d/%m')
        except:
            return ''
    else:
        return ''


def convert_date_to_DDMM(date_string, date_format):
    # Handle formatting without spaces
    date_format = date_format.replace(' ', '')
    date_string = date_string.replace(' ', '')

    date_matched_string = None
    date_format_identifier = None
    if date_format == 'DD/MM/YYYY':
        date_string = handle_zeros(date_string, [0, 3, 6, 7, 8, 9])
        matched = re.findall(r'(\d\d/\d\d/\d\d\d\d)', date_string)
        if len(matched) > 0:
            date_matched_string = matched[0]
            date_format_identifier = "%d/%m/%Y"
    elif date_format == 'D/MM/YYYY':
        if len(date_string) > 9:
            date_string = handle_zeros(date_string, [0, 3, 6, 7, 8, 9])
        else:
            date_string = handle_zeros(date_string, [2, 5, 6, 7, 8])
        matched = re.findall(r'(\d\d/\d\d/\d\d\d\d)', date_string)
        # No leading zeros
        if len(matched) == 0:
            matched = re.findall(r'(\d/\d\d/\d\d\d\d)', date_string)
        if len(matched) > 0:
            date_matched_string = matched[0]
            date_format_identifier = "%d/%m/%Y"
    elif date_format == 'DD-MM-YYYY':
        date_string = handle_zeros(date_string, [0, 1, 3, 6, 7, 8, 9])
        matched = re.findall(r'(\d\d-\d\d-\d\d\d\d)', date_string)
        if len(matched) > 0:
            date_matched_string = matched[0]
            date_format_identifier = "%d-%m-%Y"
    elif date_format == 'DDMMYY':
        date_string = handle_zeros(date_string, [0, 1, 2, 4, 5])
        matched = re.findall(r'(\d\d\d\d\d\d)', date_string)
        if len(matched) > 0:
            date_matched_string = matched[0]
            date_format_identifier = "%d%m%y"
    elif date_format == 'DD-MMM-YYYY':
        date_string = handle_zeros(date_string, [0, 1, 7, 8, 9, 10])
        matched = re.findall(r'(\d\d-[a-zA-Z][a-zA-Z][a-zA-Z]-\d\d\d\d)', date_string)
        if len(matched) > 0:
            date_matched_string = matched[0]
            date_format_identifier = "%d-%b-%Y"
    elif date_format == 'DD/MM':
        date_string = handle_zeros(date_string, [0, 1, 3])
        matched = re.findall(r'(\d\d/\d\d)', date_string)
        if len(matched) > 0:
            # Handle 29 Feb
            if matched[0] == '29/02':
                fixed_date = matched[0] + ' 2020'
                date_matched_string = fixed_date
                date_format_identifier = "%d/%m %Y"
            else:
                date_matched_string = matched[0]
                date_format_identifier = "%d/%m"
    elif date_format == 'MMMDD':
        date_string = handle_zeros(date_string, [3, 4])
        date_string = handle_ohs(date_string.lower(), [0, 1])
        matched = re.findall(r'([a-zA-Z][a-zA-Z][a-zA-Z]\d\d)', date_string)
        if len(matched) > 0:
            # Handle 29 Feb
            if matched[0].lower() == 'feb29':
                fixed_date = matched[0] + ' 2020'
                date_matched_string = fixed_date
                date_format_identifier = "%b%d %Y"
            else:
                date_matched_string = matched[0]
                date_format_identifier = "%b%d"
    elif date_format == 'DDMMM':
        date_string = handle_zeros(date_string, [0, 1])
        date_string = handle_ohs(date_string.lower(), [2, 3])
        matched = re.findall(r'(\d\d[a-zA-Z][a-zA-Z][a-zA-Z])', date_string)
        if len(matched) > 0:
            # Handle 29 Feb
            if matched[0].lower() == '29feb':
                fixed_date = matched[0] + ' 2020'
                date_matched_string = fixed_date
                date_format_identifier = "%d%b %Y"
            else:
                date_matched_string = matched[0]
                date_format_identifier = "%d%b"

    if date_matched_string and date_format_identifier:
        try:
            date_formatter = datetime.datetime.strptime(date_matched_string, date_format_identifier)
            return date_formatter.strftime('%d/%m')
        except:
            return ''
    else:
        return ''


# Utility function to handle cases where O is present instead of 0
def handle_zeros(date_string, potential_zero_indices):
    for potential_zero_index in potential_zero_indices:
        if date_string[potential_zero_index] == 'O':
            date_string = '%s%s%s' % (date_string[:potential_zero_index], '0', date_string[potential_zero_index+1:])

    return date_string


def handle_ohs(date_string, potential_oh_indices):
    for potential_oh_index in potential_oh_indices:
        if date_string[potential_oh_index] == '0':
            date_string = '%s%s%s' % (date_string[:potential_oh_index], 'o', date_string[potential_oh_index+1:])

    return date_string
