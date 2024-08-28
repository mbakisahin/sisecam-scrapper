import os
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import time
from typing import List, Tuple
from bs4 import BeautifulSoup
import json
import logging


class EchaWebScraper:
    def __init__(self, key_words: List[str], base_url: str, limited_page: int, driver):
        """
        WebScraper initializes with keywords, base URL, and site name for logging.
        Args:
            key_words (List[str]): List of keywords to search.
            base_url (str): Base URL for the web scraping.
            site_name (str): Name of the site for organizing logs.
        """
        self.base_url = base_url
        self.key_words = key_words
        self.driver = driver
        self.driver.get(self.base_url)
        self.limited_page = limited_page
        self.site_name = "ECHA"

        # Set up the logger
        self.logger = self.setup_logger(self.site_name, key_words)

    def setup_logger(self, site_name: str, key_words: List[str]) -> logging.Logger:
        """
        Sets up a logger for the scraper, creating directories for each site and keyword set.
        Args:
            site_name (str): The name of the site (e.g., 'ECHA', 'Eurlex').
            key_words (List[str]): The list of keywords for the current scraper.

        Returns:
            logging.Logger: Configured logger instance.
        """
        # Define the log directory structure
        log_dir = os.path.join("logs", site_name)
        os.makedirs(log_dir, exist_ok=True)

        # Create a log file name based on the keywords
        log_file_name = f"{'_'.join(key_words)}.log"
        log_file_path = os.path.join(log_dir, log_file_name)

        # Create a logger for this scraper
        logger = logging.getLogger(f"{site_name}_{'_'.join(key_words)}")
        logger.setLevel(logging.INFO)

        # Create a file handler that logs to a specific file
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(logging.INFO)

        # Create a stream handler to output logs to the console
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)

        # Create a logging format
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        # Add the handlers to the logger
        if not logger.handlers:
            logger.addHandler(file_handler)
            logger.addHandler(stream_handler)

        return logger

    def start(self):
        """
        Starts the web scraping process.
        """
        self.logger.info("Starting the scraping process.")
        for keyword in self.key_words:
            self.logger.info(f"Processing keyword: {keyword}")
            self.create_folder_structure(keyword)
            pdf_urls, non_pdf_urls = self.get_urls(keyword, self.limited_page)
            pdf_data = self.download_pdf_files(pdf_urls, keyword)
            self.save_pdf_data(keyword, pdf_data)
            self.process_non_pdf_urls(non_pdf_urls, keyword)
        self.driver.quit()
        self.logger.info("Scraping process completed.")

    def search_for_keyword(self, keyword: str):
        self.logger.info(f"Searching for keyword: {keyword}")
        search_box = WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "SimpleSearchText"))
        )
        search_box.clear()
        search_box.send_keys(keyword)
        search_box.send_keys(Keys.RETURN)
        time.sleep(10)

    def select_date(self, year, month, day):
        self.logger.info(f"Selecting date: {year}-{month}-{day}")
        from_date_picker = WebDriverWait(self.driver, 20).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//input[contains(@id, '_echasearch_WAR_echaportlet_updatedFrom')]"))
        )
        from_date_picker.click()
        time.sleep(2)

        year_select_element = WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//select[contains(@class, 'ui-datepicker-year')]"))
        )

        year_select = Select(year_select_element)
        year_select.select_by_value(str(year))
        time.sleep(2)

        month_select_element = WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//select[contains(@class, 'ui-datepicker-month')]"))
        )
        month_select = Select(month_select_element)
        month_select.select_by_value(str(month - 1))
        time.sleep(2)

        day_element = WebDriverWait(self.driver, 20).until(
            EC.element_to_be_clickable((By.XPATH,
                                        f"//td[@data-handler='selectDay' and @data-month='{month - 1}' and @data-year='{year}']/a[text()='{day}']"))
        )
        day_element.click()
        time.sleep(2)

    def sort_by_last_modified(self):
        self.logger.info("Sorting by last modified date.")
        sort_by_select = WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located(
                (By.XPATH, "//select[contains(@id, '_echasearch_WAR_echaportlet_sortingType')]"))
        )
        sort_by_select.click()
        last_modified_option = WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//option[@value='modified']"))
        )
        last_modified_option.click()
        time.sleep(5)

    def get_urls(self, keyword: str, limited_page: int) -> Tuple[
        List[Tuple[str, str, str, str]], List[Tuple[str, str, str, str]]]:
        """
        Extracts PDF and non-PDF URLs from search results.
        Args:
            keyword (str): Keyword to search for.

        Returns:
            Tuple[List[Tuple[str, str, str, str]], List[Tuple[str, str, str, str]]]: Lists of PDF and non-PDF URLs with metadata.
        """
        pdf_urls = []
        non_pdf_urls = []

        self.driver.get(self.base_url)
        time.sleep(5)

        try:
            self.logger.info(f"Retrieving URLs for keyword: {keyword}")
            self.search_for_keyword(keyword)
            self.select_date(2012, 8, 9)
            self.sort_by_last_modified()
            page_number = 1
            while True:
                self.logger.info(f"Processing page number: {page_number}")
                results = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, "//div[contains(@class, 'search-result-title')]//a[@href]"))
                )
                dates = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH,
                         "//div[contains(@class, 'search-result-title')]//a[@href]/../../following-sibling::td"))
                )
                descriptions = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, "//div[contains(@class, 'search-result-content')]"))
                )

                for result, date, description in zip(results, dates, descriptions):
                    link = result.get_attribute("href")
                    name = result.text.strip()
                    description_text = description.text.strip()

                    if link.startswith('/'):
                        link = 'https://echa.europa.eu' + link
                    formatted_date = date.text.strip().replace('/', '-')
                    day, month, year = formatted_date.split('-')
                    year = '20' + year
                    formatted_date = f"{year}-{month}-{day}"

                    if link.split('/')[-2].endswith('.pdf'):
                        pdf_urls.append((link, formatted_date, name, description_text))
                    else:
                        non_pdf_urls.append((link, formatted_date, name, description_text))

                self.logger.info(f"Found {len(pdf_urls)} PDF URLs and {len(non_pdf_urls)} non-PDF URLs.")

                if limited_page == 0:
                    limited_page = float('inf')

                if page_number < limited_page:
                    page_number += 1
                    next_button = self.driver.find_elements(By.XPATH, "//a[contains(text(), 'Next')]")
                    if next_button and 'disabled' not in next_button[0].get_attribute('class') and next_button[
                        0].get_attribute('href') != "javascript:;":
                        next_button[0].click()
                        time.sleep(5)
                    else:
                        break
                else:
                    break
        except Exception as e:
            self.log_error(e, self.driver.current_url)

        return pdf_urls, non_pdf_urls

    def download_pdf_files(self, urls: List[Tuple[str, str, str, str]], keyword: str) -> List[dict]:
        """
        Downloads PDF files from the provided URLs.
        Args:
            urls (List[Tuple[str, str, str]]): List of URLs to download.
            keyword (str): Keyword for creating folder structure.

        Returns:
            List[dict]: List of downloaded PDF data.
        """
        self.logger.info(f"Downloading PDF files for keyword: {keyword}")
        data = []
        for url, date, name, description in urls:
            try:
                pdf_response = requests.get(url)
                data.append({
                    'url': url,
                    'date': date,
                    'file_name': name,
                    'content': pdf_response.content
                })
                self.logger.info(f"Downloaded: {name}")
                self.save_metadata(keyword, {
                    "name": name,
                    "notified_date": date,
                    "notified_country": None,
                    "URL": url,
                    "keyword": keyword
                })
            except Exception as e:
                self.log_error(e, url)
        return data

    def process_non_pdf_urls(self, urls: List[Tuple[str, str, str, str]], keyword: str):
        """
        Processes non-PDF URLs to extract summaries and tables.
        Args:
            urls (List[Tuple[str, str, str]]): List of URLs to process.
            keyword (str): Keyword for creating folder structure.
        """
        self.logger.info(f"Processing non-PDF URLs for keyword: {keyword}")
        for url, date, name, description in urls:
            try:
                response = requests.get(url)
                soup = BeautifulSoup(response.content, 'html.parser')

                self.save_summary(keyword, url, date, name, description)
                self.extract_and_save_tables(soup, keyword, name, date)
                self.logger.info(f"Extracted summary and checked for tables from: {url}")
                self.save_metadata(keyword, {
                    "name": name,
                    "notified_date": date,
                    "notified_country": None,
                    "URL": url,
                    "keyword": keyword
                })
            except Exception as e:
                self.log_error(e, url)

    def extract_and_save_tables(self, soup: BeautifulSoup, keyword: str, name: str, date: str):
        """
        Extracts and saves tables from the provided page soup into a single JSON file.
        Args:
            soup (BeautifulSoup): BeautifulSoup object of the page.
            keyword (str): Keyword for creating folder structure.
            name (str): Name for the file.
            date (str): Date of the page.
        """
        self.logger.info(f"Extracting tables from page: {name}")
        tables_data = []

        tables = soup.find_all('table')
        for i, table in enumerate(tables):
            headers = [th.get_text().strip() for th in table.find_all('th')]
            rows = [
                [cell.get_text().strip() for cell in row.find_all('td')]
                for row in table.find_all('tr') if row.find_all('td')
            ]

            if rows and headers:
                table_data = {
                    'headers': headers,
                    'rows': rows
                }
                tables_data.append(table_data)

        if tables_data:
            keyword_folder = os.path.join('data/raw/ECHA', keyword.replace(':', '').replace(' ', '_'), 'json')
            os.makedirs(keyword_folder, exist_ok=True)
            table_file_name = os.path.join(keyword_folder, f"{date}-{name}.json")

            with open(table_file_name, 'w', encoding='utf-8') as table_file:
                json.dump(tables_data, table_file, ensure_ascii=False, indent=4)
            self.logger.info(f"Saved tables to {table_file_name}")

    def save_summary(self, keyword: str, url: str, date: str, name: str, description: str):
        """
        Saves summary to a text file.
        Args:
            keyword (str): Keyword for creating folder structure.
            url (str): URL of the page.
            date (str): Date of the page.
            summary (str): Extracted summary.
        """
        self.logger.info(f"Saving summary for: {name}")
        keyword_folder = os.path.join('data/raw/ECHA', keyword.replace(':', '').replace(' ', '_'), 'text')
        os.makedirs(keyword_folder, exist_ok=True)
        summary_file_name = os.path.join(keyword_folder, f"{date}-{name}.txt")

        with open(summary_file_name, 'w', encoding='utf-8') as summary_file:
            summary_file.write(f"Title: {name}\n")
            summary_file.write(f"Distribution date: {date}\n")
            summary_file.write(f"Keywords:: {keyword}\n")
            summary_file.write(f"Summary: {description}\n")
        self.logger.info(f"Summary saved to {summary_file_name}")

    def save_pdf_data(self, keyword: str, data: List[dict]):
        """
        Saves PDF data to files.
        Args:
            keyword (str): Keyword for creating folder structure.
            data (List[dict]): List of PDF data to save.
        """
        self.logger.info(f"Saving PDF data for keyword: {keyword}")
        keyword_folder = os.path.join('data/raw/ECHA', keyword.replace(':', '').replace(' ', '_'), 'pdf')
        os.makedirs(keyword_folder, exist_ok=True)

        for item in data:
            pdf_name = os.path.join(keyword_folder, f"{item['date']}-{item['file_name']}")
            with open(pdf_name, 'wb') as pdf_file:
                pdf_file.write(item['content'])
            self.logger.info(f"PDF saved to {pdf_name}")

    def save_metadata(self, keyword: str, metadata: dict):
        """
        Saves metadata to a JSON file.
        Args:
            keyword (str): Keyword for creating folder structure.
            metadata (dict): Metadata to save.
        """
        self.logger.info(f"Saving metadata for: {metadata['name']}")
        metadata_folder = os.path.join('data/raw/ECHA', keyword.replace(':', '').replace(' ', '_'), 'metadata')
        os.makedirs(metadata_folder, exist_ok=True)
        metadata_file_name = os.path.join(metadata_folder,
                                          f"metadata_{metadata['notified_date']}-{metadata['name']}.json")

        with open(metadata_file_name, 'w', encoding='utf-8') as metadata_file:
            json.dump(metadata, metadata_file, ensure_ascii=False, indent=4)
        self.logger.info(f"Metadata saved to {metadata_file_name}")


    def log_error(self, error: Exception, url: str):
        """
        Logs error to the console.
        Args:
            error (Exception): The caught exception.
            url (str): URL where the error occurred.
        """
        self.logger.error(f"An error occurred while processing {url}: {str(error)}")

    def create_folder_structure(self, keyword: str):
        """
        Creates folder structure for the keyword.
        Args:
            keyword (str): Keyword for creating folder structure.
        """
        self.logger.info(f"Creating folder structure for keyword: {keyword}")
        keyword_folder = os.path.join('data/raw/ECHA', keyword.replace(':', '').replace(' ', '_'))
        os.makedirs(keyword_folder, exist_ok=True)
        os.makedirs(os.path.join(keyword_folder, 'pdf'), exist_ok=True)
        os.makedirs(os.path.join(keyword_folder, 'text'), exist_ok=True)
        os.makedirs(os.path.join(keyword_folder, 'metadata'), exist_ok=True)
        os.makedirs(os.path.join(keyword_folder, 'json'), exist_ok=True)
