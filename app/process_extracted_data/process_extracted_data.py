from .handle_data_functions import *
from app.extract_data import extract_text_scanned
import cv2


def process_text(text_extracted_list, configuration_fields, pdf_type, extracted_table=None, summary_lines=None):
    print('[INFO] Postprocessing start')
    final_result = {}
    final_result.update({"statement-results": []})
    start_statement_keyword_list = configuration_fields["transaction-config"]["start-of-month-keyword"]
    end_statement_keyword_list = configuration_fields["transaction-config"]["end-of-month-keyword"]
    state_date_format = configuration_fields["transaction-config"]["statement-date-format"]
    for i in range(len(text_extracted_list)):
        # Pass in last transaction from last page in case there are overflows into the next page
        last_page_last_txn = None

        # Handle cases where there might be pages without transactions in between
        last_page_with_txn_index = -1
        if len(final_result["statement-results"]) > 0:
            for j in range((len(final_result['statement-results']) - 1), -1, -1):
                if len(final_result['statement-results'][j]['transactions']) > 0:
                    last_page_with_txn_index = j
                    break
            if last_page_with_txn_index >= 0 and 'page-last-transaction-index' in configuration_fields['transaction-config']:
                if len(final_result["statement-results"][last_page_with_txn_index]["transactions"]) > 0:
                    last_page_last_txn = final_result["statement-results"][last_page_with_txn_index]["transactions"][configuration_fields['transaction-config']['page-last-transaction-index']]

        if extracted_table and len(extracted_table) >= len(text_extracted_list):
            processedData, lplt_updated = process_page(text_extracted_list[i], configuration_fields, [pdf_type], last_page_last_txn, extracted_table[i])
        else:
            processedData, lplt_updated = process_page(text_extracted_list[i], configuration_fields, [pdf_type], last_page_last_txn)

        # Update lplt if applicable
        if lplt_updated:
            final_result["statement-results"][last_page_with_txn_index]["transactions"][configuration_fields['transaction-config']['page-last-transaction-index']] = lplt_updated

        keyword_found_start = False
        keyword_found_end = False
        keyword_isolated = False
        for transaction in processedData["final-transaction"]:
            if not keyword_found_start:
                for keyword in start_statement_keyword_list:
                    if transaction['transaction-description-1'] is not None and keyword in transaction['transaction-description-1']:
                        keyword_found_start = True
        for keyword in end_statement_keyword_list:
            if processedData["final-transaction"] != [] and\
                    processedData["final-transaction"][0]['transaction-description-1'] is not None and\
                    keyword in processedData["final-transaction"][0]['transaction-description-1']:
                keyword_isolated = True
            if not keyword_found_end:
                if len(final_result["statement-results"]) > 0 and len(final_result["statement-results"][-1]['transactions']) > 0 and final_result["statement-results"][-1]['transactions'][-1]["transaction-description-1"] is not None:
                    if keyword in final_result["statement-results"][-1]['transactions'][-1]["transaction-description-1"]:
                        keyword_found_end = True
        if len(processedData["final-transaction"]) > 0:
            processedData["final-summary"] = parsing.find_transaction_summary_info(processedData, configuration_fields)
            if (final_result["statement-results"] == [] or keyword_found_start or keyword_found_end) and not (keyword_isolated and keyword_found_end):
                if len(processedData["final-transaction"]) > 0:
                    processedData["final-summary"]["number-of-pages"] = 1
                if pdf_type != 'PDF - Native' and 'cropped-summary-areas' in configuration_fields:
                    input_img = cv2.imread(processedData["final-transaction"][0]['file-name'], 0)
                    cropped_summary_areas = configuration_fields['cropped-summary-areas']
                    for key in cropped_summary_areas:
                        if key != 'crop-account-name-address-area' and len(cropped_summary_areas[key]['coordinates']) > 0:
                            extract_text = extract_text_scanned.extract_summary_field(cropped_summary_areas[key], input_img)
                            processedData["final-summary"][cropped_summary_areas[key]['field-name']] = extract_text
                if 'statement-date' in processedData["final-summary"]:
                    processedData["final-summary"]['statement-date'] = process.convert_date_to_DDMMYY(processedData["final-summary"]['statement-date'], state_date_format)

                # Add details to final summary if applicable
                if summary_lines and len(summary_lines) > 0:
                    # Get account name and address
                    account_name = ''
                    account_address = ''
                    start_index = -1

                    if 'account-name-address-remove' in configuration_fields['summary-config']:
                        # Run noise removal if multiple spaces present
                        run_noise_removal = False
                        for summary_line in summary_lines:
                            if "  " in summary_line:
                                run_noise_removal = True
                                break

                        cleaned_summary_lines = []
                        clean_complete = False
                        if run_noise_removal:
                            # Use brute force implementation
                            summary_text_to_remove = configuration_fields['summary-config']['account-name-address-remove']
                            add_line = False
                            for j, summary_line in enumerate(summary_lines):
                                summary_line = summary_line.strip()

                                if not add_line and configuration_fields['summary-config']['account-name-start'] in summary_line:
                                    add_line = True
                                    continue

                                if not add_line and 'account-name-line-start-index' in configuration_fields['summary-config']:
                                    if j == configuration_fields['summary-config']['account-name-line-start-index']:
                                        add_line = True

                                # Clean noise
                                summary_line_space_split = summary_line.split('  ')
                                if len(summary_line_space_split) > 1:
                                    summary_line = summary_line_space_split[0].strip()

                                for text_to_remove in summary_text_to_remove:
                                    if text_to_remove in summary_line:
                                        summary_line = ''
                                        break

                                for stop_keyword in configuration_fields['summary-config']['account-address-stop']:
                                    if stop_keyword in summary_line:
                                        clean_complete = True
                                        break

                                if clean_complete:
                                    break

                                if add_line and len(summary_line) > 0 and not summary_line.isdigit():
                                    cleaned_summary_lines.append(summary_line)
                        else:
                            for summary_line in summary_lines:
                                cleaned_summary_lines.append(summary_line.strip())

                        if len(cleaned_summary_lines) > 0:
                            add_to_address = False
                            for cleaned_summary_line in cleaned_summary_lines:
                                split_line = cleaned_summary_line.split(' ')
                                if add_to_address is False and len(split_line) > 1:
                                    if split_line[0].replace(',', '').isdigit():
                                        add_to_address = True
                                    elif split_line[0].replace(',', '')[:-2].isdigit():
                                        # Handle case where address is followed by one letter
                                        add_to_address = True

                                if not add_to_address:
                                    account_name += cleaned_summary_line.strip()
                                    account_name += ' '
                                else:
                                    account_address += cleaned_summary_line.strip()
                                    account_address += ', '
                    else:
                        if 'separate-summary-lines' in configuration_fields['summary-config'] and configuration_fields['summary-config']['separate-summary-lines'] is True:
                            if 'account-name-start' in configuration_fields['summary-config']:
                                if len(configuration_fields['summary-config']['account-name-start']) > 0:
                                    for j, summary_line in enumerate(summary_lines):
                                        if configuration_fields['summary-config']['account-name-start'] in summary_line:
                                            start_index = j
                                            break
                                else:
                                    start_index = 0

                                # Verify start index is not empty, then
                                if len(summary_lines[start_index + configuration_fields['summary-config']['account-name-line-start-index']].strip()) == 0:
                                    start_index += 1

                                if start_index >= 0:
                                    for j in range(start_index + configuration_fields['summary-config']['account-name-line-start-index'], start_index + configuration_fields['summary-config']['account-name-line-end-index'] + 1):
                                        if 'requires-space-separation' in configuration_fields['summary-config'] and configuration_fields['summary-config']['requires-space-separation'] is True:
                                            space_split_line = summary_lines[j].strip().split('  ')
                                            if len(space_split_line) > 1:
                                                account_name += space_split_line[0]
                                            else:
                                                account_name += summary_lines[j].strip()
                                        else:
                                            account_name += summary_lines[j].strip()

                                        # Remove account name start identifier if exists
                                        if 'account-name-start' in configuration_fields['summary-config'] and len(configuration_fields['summary-config']['account-name-start']) > 0 and configuration_fields['summary-config']['account-name-start'] in account_name:
                                            split_account_name = account_name.split(configuration_fields['summary-config']['account-name-start'])
                                            account_name = split_account_name[1].strip()

                                        account_name += ' '

                                # Remove account name end identifier if exists
                                if 'account-name-end' in configuration_fields['summary-config'] and len(configuration_fields['summary-config']['account-name-end']) > 0 and configuration_fields['summary-config']['account-name-end'] in account_name:
                                    split_account_name = account_name.split(configuration_fields['summary-config']['account-name-end'])
                                    account_name = split_account_name[0].strip()

                            if 'account-address-stop' in configuration_fields['summary-config']:
                                for j in range(start_index + configuration_fields['summary-config']['account-address-line-start-index'], len(summary_lines)):
                                    if len(configuration_fields['summary-config']['account-address-stop']) == 0:
                                        stripped_line = summary_lines[j].strip()

                                        if len(stripped_line) > 0:
                                            # Check if should stop at name
                                            if 'account-address-stop-at-name' in configuration_fields['summary-config'] and \
                                                    configuration_fields['summary-config']['account-address-stop-at-name'] is True:
                                                if stripped_line == account_name.strip():
                                                    break

                                            account_address += summary_lines[j].strip()
                                            account_address += ', '
                                        else:
                                            break
                                    else:
                                        stop_keyword_found = False
                                        for stop_keyword in configuration_fields['summary-config']['account-address-stop']:
                                            if stop_keyword in summary_lines[j]:
                                                stop_keyword_found = True
                                                break

                                        if not stop_keyword_found:
                                            if 'requires-space-separation' in configuration_fields['summary-config'] and configuration_fields['summary-config']['requires-space-separation'] is True:
                                                space_split_line = summary_lines[j].strip().split('  ')
                                                if len(space_split_line) > 1:
                                                    account_address += space_split_line[0]
                                                else:
                                                    account_address += summary_lines[j].strip()
                                            else:
                                                account_address += summary_lines[j].strip()

                                            account_address += ', '
                                        else:
                                            break

                    account_name = account_name.strip()
                    account_address = account_address.strip(', ')

                    processedData['final-summary']['account-name'] = account_name
                    processedData['final-summary']['account-address'] = account_address

                if 'add-initial-summary' in configuration_fields['summary-config'] and \
                        configuration_fields['summary-config']['add-initial-summary'] is True and \
                        len(final_result['statement-results']) > 0 and 'summary' in final_result['statement-results'][-1]:
                    # Update summary if applicable
                    last_summary = final_result['statement-results'][-1]['summary']
                    for key in processedData['final-summary'].keys():
                        if len(str(processedData['final-summary'][key])) > 0:
                            last_summary.update({key: processedData['final-summary'][key]})

                    # Replace transactions
                    final_result['statement-results'][-1]['transactions'] = processedData['final-transaction']
                else:
                    # Add default bank name
                    if 'bank-name' in processedData['final-summary'] and processedData['final-summary']['bank-name'] == '':
                        processedData['final-summary']['bank-name'] = configuration_fields['init-config']['bank-name']
                    final_result["statement-results"].append(
                        {
                            'summary':  processedData["final-summary"],
                            'transactions': processedData["final-transaction"]
                        }
                    )
            else:
                final_result["statement-results"][-1]["transactions"].extend(processedData["final-transaction"])
                current_transactions = final_result["statement-results"][-1]["transactions"]
                if len(current_transactions) > 0:
                    final_result["statement-results"][-1]["summary"]["number-of-pages"] = current_transactions[-1]['page'] - current_transactions[0]['page'] + 1
                    for key in processedData["final-summary"]:
                        if key not in final_result["statement-results"][-1]["summary"] or \
                                (key in final_result["statement-results"][-1]["summary"] and len(str(final_result["statement-results"][-1]["summary"][key])) == 0):
                            final_result["statement-results"][-1]["summary"][key] = processedData["final-summary"][key]
        else:
            # Add initial summary if applicable
            has_native_summary = False
            if summary_lines and len(summary_lines) > 0:
                for summary_line in summary_lines:
                    if "  " in summary_line:
                        has_native_summary = True
                        break
            if 'add-initial-summary' in configuration_fields['summary-config'] and \
                    configuration_fields['summary-config']['add-initial-summary'] is True and \
                    len(processedData['final-summary']) > 0 and i < len(text_extracted_list) - 1:
                processedData["final-summary"]["number-of-pages"] = 1

                # Skip if native summary does not have date
                if has_native_summary and ('statement-date' not in processedData["final-summary"] or len(processedData['final-summary']['statement-date']) == 0):
                    continue

                if 'statement-date' in processedData["final-summary"] and len(processedData['final-summary']['statement-date']) > 0:
                    processedData["final-summary"]['statement-date'] = process.convert_date_to_DDMMYY(processedData["final-summary"]['statement-date'], state_date_format)

                # Add default bank name
                if 'bank-name' in processedData['final-summary'] and processedData['final-summary']['bank-name'] == '':
                    processedData['final-summary']['bank-name'] = configuration_fields['init-config']['bank-name']
                final_result["statement-results"].append(
                    {
                        'summary': processedData["final-summary"],
                        'transactions': []
                    }
                )

    for i, transaction_month in enumerate(final_result["statement-results"]):
        initial_transactions_list = transaction_month["transactions"]
        transactions_list = []

        remove_date_key_words = configuration_fields['transaction-config']['txn-remove-date'] if 'txn-remove-date' in configuration_fields['transaction-config'] else None
        remove_key_words = configuration_fields['transaction-config']['txn-remove'] if 'txn-remove' in configuration_fields['transaction-config'] else None

        if remove_date_key_words or remove_key_words:
            for txn in initial_transactions_list:
                add_txn = True
                if remove_date_key_words:
                    for remove_date_key_word in remove_date_key_words:
                        if 'transaction-description-1' in txn and txn['transaction-description-1'] is not None \
                           and remove_date_key_word in txn['transaction-description-1']:
                            txn['transaction-date'] = None
                            break

                if remove_key_words:
                    txn_description_prefix = 'transaction-description-'
                    for remove_key_word in remove_key_words:
                        description_index = 1
                        current_txn_description = txn_description_prefix + str(description_index)
                        while current_txn_description in txn:
                            if txn[current_txn_description] is not None and remove_key_word in txn[current_txn_description]:
                                add_txn = False
                                break
                            description_index += 1
                            current_txn_description = txn_description_prefix + str(description_index)

                if add_txn:
                    transactions_list.append(txn)
        else:
            transactions_list = initial_transactions_list

        transactions_list = process.extract_transaction_type_and_error(transactions_list, configuration_fields)

        # Run number model to attempt transaction error correction
        transactions_list = process.run_number_model(transactions_list, configuration_fields, "box")
        transactions_list = process.run_number_model(transactions_list, configuration_fields, "line")

        # Run any summary postprocessing if applicable
        summary_config = configuration_fields['summary-config']
        transaction_month_summary = transaction_month['summary']

        if 'balance-postprocessing-opening-balance' in summary_config and \
                summary_config['balance-postprocessing-opening-balance'] is True:
            # Opening balance
            postprocessing_start_balance = 0
            if 'opening-balance-key-word' in summary_config:
                opening_balance_key_word = summary_config['opening-balance-key-word']
                for transaction in transactions_list:
                    if opening_balance_key_word in transaction['transaction-description-1']:
                        postprocessing_start_balance = transaction['transaction-balance']
                        if 'in-debt' in transaction and transaction['in-debt'] is True:
                            postprocessing_start_balance *= -1
                        break
            elif 'opening-balance-calculate' in summary_config and summary_config['opening-balance-calculate'] is True:
                # Calculate opening balance based on total withdrawals and credits
                total_debit = float(transaction_month_summary['total-debit']) if 'total-debit' in transaction_month_summary else None
                total_credit = float(transaction_month_summary['total-credit']) if 'total-credit' in transaction_month_summary else None

                if total_debit and total_credit:
                    # Find first and last statement with date
                    first_txn = None
                    last_txn = None
                    for transaction in transactions_list:
                        if 'transaction-date' in transaction and transaction['transaction-date'] is not None and len(
                                transaction['transaction-date']) > 0:
                            first_txn = transaction
                            break

                    for k in range(len(transactions_list) - 1, -1, -1):
                        transaction = transactions_list[k]
                        if 'transaction-date' in transaction and transaction['transaction-date'] is not None and len(
                                transaction['transaction-date']) > 0:
                            last_txn = transaction
                            break

                    last_transaction_balance = float(last_txn['transaction-balance'])
                    if last_txn['in-debt']:
                        last_transaction_balance *= -1
                    opening_balance_calculated = last_transaction_balance - total_credit + total_debit
                    postprocessing_start_balance = float('%.02f' % round(opening_balance_calculated, 2))

                    # Fill in transaction information for first transaction
                    opening_balance_in_debt = opening_balance_calculated < 0
                    if first_txn['in-debt'] and opening_balance_in_debt:
                        if (opening_balance_calculated - float(first_txn['transaction-balance'])) < 0:
                            first_txn['transaction-type'] = 'Debit'
                        elif (opening_balance_calculated - float(first_txn['transaction-balance'])) > 0:
                            first_txn['transaction-type'] = 'Credit'
                    elif first_txn['in-debt'] and not opening_balance_in_debt:
                        first_txn['transaction-type'] = 'Debit'
                    elif not first_txn['in-debt'] and opening_balance_in_debt:
                        first_txn['transaction-type'] = 'Credit'
                    else:
                        if (opening_balance_calculated - float(first_txn['transaction-balance'])) > 0:
                            first_txn['transaction-type'] = 'Debit'
                        elif (opening_balance_calculated - float(first_txn['transaction-balance'])) < 0:
                            first_txn['transaction-type'] = 'Credit'

                    transaction_amount = first_txn['transaction-amount']
                    transaction_match_1 = (
                                round(abs(float(first_txn['transaction-balance']) - opening_balance_calculated), 2) == float(
                            transaction_amount))
                    transaction_match_2 = (
                                round(abs(float(first_txn['transaction-balance']) + opening_balance_calculated), 2) == float(
                            transaction_amount))
                    if transaction_match_1 or transaction_match_2:
                        first_txn['transaction-error'] = False
                    else:
                        first_txn['transaction-error'] = True
            else:
                # Take first item with date
                for transaction in transactions_list:
                    if 'transaction-date' in transaction and transaction['transaction-date'] is not None and len(transaction['transaction-date']) > 0:
                        postprocessing_start_balance = transaction['transaction-balance']
                        if 'in-debt' in transaction and transaction['in-debt'] is True:
                            postprocessing_start_balance *= -1
                        break

            # Update opening balance in summary
            if postprocessing_start_balance != 0:
                transaction_month_summary.update({'start-balance': postprocessing_start_balance})

        if 'balance-postprocessing-closing-balance' in summary_config and \
                summary_config['balance-postprocessing-closing-balance'] is True:
            postprocessing_close_balance = 0
            if 'closing-balance-key-word' in summary_config:
                closing_balance_key_word = summary_config['closing-balance-key-word']
                for k in range(len(transactions_list) - 1, -1, -1):
                    transaction = transactions_list[k]
                    if closing_balance_key_word in transaction['transaction-description-1']:
                        postprocessing_close_balance = transaction['transaction-balance']
                        if 'in-debt' in transaction and transaction['in-debt'] is True:
                            postprocessing_close_balance *= -1
                        break
            else:
                # Take last item with date
                for k in range(len(transactions_list) - 1, -1, -1):
                    transaction = transactions_list[k]
                    if 'transaction-date' in transaction and transaction['transaction-date'] is not None and len(transaction['transaction-date']) > 0:
                        postprocessing_close_balance = transaction['transaction-balance']
                        if 'in-debt' in transaction and transaction['in-debt'] is True:
                            postprocessing_close_balance *= -1
                        break

            # Update closing balance in summary
            if postprocessing_close_balance != 0:
                transaction_month_summary.update({'close-balance': postprocessing_close_balance})

        if 'balance-postprocessing-credit-debit' in summary_config and \
                summary_config['balance-postprocessing-credit-debit'] is True:
            total_credit = 0
            total_debit = 0
            for transaction in transactions_list:
                if 'transaction-date' in transaction and transaction['transaction-date'] is not None and len(transaction['transaction-date']) > 0:
                    if transaction['transaction-type'] == 'Credit':
                        total_credit += float(transaction['transaction-amount'])
                    elif transaction['transaction-type'] == 'Debit':
                        total_debit += float(transaction['transaction-amount'])

            transaction_month_summary.update({
                'total-credit': float('%.02f' % round(total_credit, 2)),
                'total-debit': float('%.02f' % round(total_debit, 2))
            })
        
        # Calculating transaction errors
        txn_error_count = 0
        for transaction in transactions_list:
            if transaction['transaction-error'] is True:
                txn_error_count += 1

        if txn_error_count == 0:
            print('--- No transaction errors found ---')
        else:
            print('--- %d transaction errors found ---' % txn_error_count)

        final_result["statement-results"][i]['transactions'] = process.convert_descriptions_to_list(transactions_list)

    print('[INFO] Postprocessing end')

    return final_result


def process_page(text_extracted_list, configuration_fields, pdfcheck, last_page_last_txn, extracted_table=None):
    processedData = {
        "final-summary": {},
        "final-transaction": []
    }

    text_list = []
    file_list = []
    position_list = []
    page_number_list = []
    txn_amount_coordinate_list = []
    txn_balance_coordinate_list = []

    for value in text_extracted_list:
        text_list.append(value['text'])
        file_list.append(value['filename'])
        position_list.append(value['position'])
        page_number_list.append(value['page-number'])
        if 'txn-balance-coordinate' in value:
            txn_balance_coordinate_list.append(value['txn-balance-coordinate'])
        else:
            txn_balance_coordinate_list.append([])
        if 'txn-amt-coordinate' in value:
            txn_amount_coordinate_list.append(value['txn-amt-coordinate'])
        else:
            txn_amount_coordinate_list.append([])

    # summary area
    bank = parsing.bank_alt_name_find(configuration_fields["summary-config"]["bank-name-find"], configuration_fields['init-config']['bank-name'], text_list)
    processedData["final-summary"]["bank-name"] = bank

    bank_address = ''
    if 'bank-address' in configuration_fields['summary-config']:
        bank_address = parsing.bank_address_find(configuration_fields["summary-config"], text_list)
    processedData["final-summary"]["bank-address"] = bank_address

    page_list, state_date, acct_type, extracted_account_number = parsing.bank_info_find(configuration_fields, text_list)
    processedData["final-summary"]["statement-date"] = state_date
    processedData["final-summary"]["account-type"] = acct_type
    processedData["final-summary"]["document-type"] = ''.join(pdfcheck)
    processedData["final-summary"]["account-name"] = ''
    processedData["final-summary"]["account-address"] = ''
    processedData["final-summary"]["account-number"] = extracted_account_number

    if pdfcheck == ['PDF - Native']:
        if 'account-type-label' in configuration_fields['summary-config']:
            account_type_config = configuration_fields['summary-config']['account-type-label']
            account_type = parsing.find_field_based_on_label(account_type_config['label'],account_type_config['index'], text_list, account_type_config['extra-line'])
            processedData["final-summary"]["account-type"] = account_type

        if 'account-number-label' in configuration_fields['summary-config']:
            account_number_config = configuration_fields['summary-config']['account-number-label']
            account_no = parsing.find_field_based_on_label(account_number_config['label'],account_number_config['index'], text_list, account_number_config['extra-line'])
            processedData["final-summary"]["account-number"] = account_no

        if 'account-holder-name-label' in configuration_fields['summary-config']:
            account_holder_name_config = configuration_fields['summary-config']['account-holder-name-label']
            account_holder_name = parsing.find_field_based_on_label(account_holder_name_config['label'], account_holder_name_config['index'], text_list, account_holder_name_config['extra-line'])
            processedData["final-summary"]["account-name"] = account_holder_name

        if 'account-holder-addr-label' in configuration_fields['summary-config']:
            account_holder_addr_config = configuration_fields['summary-config']['account-holder-addr-label']
            account_holder_name = parsing.find_field_based_on_label(account_holder_addr_config['label'], account_holder_addr_config['index'], text_list, account_holder_addr_config['extra-line'])
            processedData["final-summary"]["account-address"] = account_holder_name

    # transaction area
    txn_list, lplt_updated = parsing.txn_find(configuration_fields["init-config"]["bank-name"],
                                              configuration_fields["transaction-config"]["txn-key-word"],
                                              configuration_fields["transaction-config"]["stop-at"],
                                              configuration_fields["transaction-config"]["date-regex-list"],
                                              configuration_fields["transaction-config"]["number-regex-list"],
                                              configuration_fields["transaction-config"]["txn-type-in-money-value"],
                                              configuration_fields["transaction-config"]["date-joined-with-transaction"],
                                              configuration_fields["transaction-config"]["balance-outside-table-key-word"],
                                              configuration_fields,
                                              text_list,
                                              extracted_table,
                                              last_page_last_txn,
                                              file_list,
                                              txn_amount_coordinate_list,
                                              txn_balance_coordinate_list,
                                              position_list,
                                              page_number_list)

    processedData["final-transaction"] = txn_list

    return processedData, lplt_updated
