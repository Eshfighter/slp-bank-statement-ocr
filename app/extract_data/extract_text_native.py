import pdftotext
import pdfplumber
from decimal import Decimal
import re


def pdf_to_text_table(filename, configuration_fields, table_settings, keywords=None, debug=False):
    # Sanity check
    if not table_settings:
        return None

    pages = []
    with pdfplumber.open(filename) as pdf:
        if keywords:
            # Process with explicit vertical lines
            for index, page in enumerate(pdf.pages):
                words = page.extract_words(x_tolerance=1)
                explicit_vertical_lines = []
                keyword_index = 0
                for word in words:
                    if keywords[keyword_index] in word['text']:
                        explicit_vertical_lines.append(word['x0'])
                        keyword_index += 1

                    if len(explicit_vertical_lines) == len(keywords):
                        break

                # Replace first line with 0 and add last line as width of page
                explicit_vertical_lines[0] = Decimal('12')
                explicit_vertical_lines.append(Decimal(str(float(page.width) - 12)))

                # Extract table
                table_settings.update({
                    "explicit_vertical_lines": explicit_vertical_lines
                })
                table = page.extract_table(table_settings)
                table_cleaned = []

                # Remove lines that are not from table
                add_line = False
                date_regex_list = configuration_fields['transaction-config']['date-regex-list']
                stop_at_list = configuration_fields['transaction-config']['stop-at']
                for line in table:
                    if not add_line:
                        # Check if date present, defining first line
                        if len(line[0]) > 0:
                            if len(re.findall(date_regex_list[0], line[0])) == 1:
                                add_line = True
                                table_cleaned.append(line)
                    else:
                        # Don't add blank lines
                        empty = True
                        stop = False
                        for elem in line:
                            if len(elem) > 0:
                                empty = False
                                if elem in stop_at_list:
                                    stop = True
                                    break

                        if not empty and not stop:
                            # Add line
                            table_cleaned.append(line)

                pages.append(table_cleaned)

                # Debug
                if debug:
                    # Words
                    page.to_image().draw_rects(words).save('words_page-%s.png' % index)

                    # Table
                    tables = page.find_tables(table_settings)
                    page.to_image().debug_table(tables[0]).save('table_page-%s.png' % index)

                    # Print lines for debug purposes
                    for line in table_cleaned:
                        print(line)
        else:
            # Process normally
            for page in pdf.pages:
                table = page.extract_table(table_settings)
                pages.append(table)

    return pages


def pdf_to_text_summary_page(filename, page_index=0):
    with open(filename, "rb") as f:
        pdf = pdftotext.PDF(f)
        page = pdf[page_index]
        return page.split('\n')


def pdf_to_text(filename):
    print('[INFO] Initial native text extraction start')
    pass_one_success = 0
    pdf_output = []
    with open(filename, "rb") as f:
        pdf = pdftotext.PDF(f)

        number_of_pages = len(pdf)
        print('--- Total number of pages: %d ---' % number_of_pages)

        # Iterate over all the pages
        for i, page in enumerate(pdf):
            print("--- Processing page %d ---" % (i+1))
            page_output = []

            if len(page) > 50:
                print("--- Text Found ---")
                pass_one_success = 1
                split_page = page.split("\n")
                for line in split_page:
                    line_info = {
                        'text': line,
                        'position': {
                            'top': None,
                            'height': None
                        },
                        'filename': None,
                        'page-number': i+1,
                    }
                    page_output.append(line_info)

                # to suit scanned format
                pdf_output.append(page_output)
            else:
                print("--- Empty ---")

    print('[INFO] Native text extraction end')

    if pass_one_success == 1:
        return {
            "page-output": pdf_output,
            "number-of-pages": number_of_pages
        }
    else: 
        return []
