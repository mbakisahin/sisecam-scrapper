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


class EurWebScraper:
    def __init__(self, key_words: List[str], base_url: str, limited_page: int, driver):
        """
        Initializes the WebScrapereur class with keywords for searching.

        Args:
            key_words (List[str]): List of keywords to be used in the search.
        """
        self.base_url = base_url
        self.key_words = key_words
        self.driver = driver
        self.driver.maximize_window()
        self.driver.get(self.base_url)
        self.limited_page = limited_page

        # Set up the logger
        self.logger = self.setup_logger("eur_lex", key_words)

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
        Initiates the web scraping process for each keyword.
        """
        self.logger.info("Starting the scraping process.")
        for keyword in self.key_words:
            self.logger.info(f"Processing keyword: {keyword}")
            self.create_folder_structure(keyword)
            pdf_urls, non_pdf_urls = self.get_urls(keyword, self.limited_page)
            pdf_data = self.download_pdf_files(pdf_urls)
            self.save_pdf_data(keyword, pdf_data)
            self.process_non_pdf_urls(non_pdf_urls, keyword)
        self.driver.quit()
        self.logger.info("Scraping process completed.")

    def search_for_keyword(self, keyword: str):
        """
        Searches for a specific keyword on the website.

        Args:
            keyword (str): The keyword to search for.
        """
        self.logger.info(f"Searching for keyword: {keyword}")
        search_box = WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.ID, "QuickSearchField"))
        )
        search_box.clear()
        search_box.send_keys(keyword)
        search_box.send_keys(Keys.RETURN)
        time.sleep(10)

    def sort_by_last_modified(self):
        """
        Sorts the search results by last modified date.
        """
        self.logger.info("Sorting results by last modified date.")
        try:
            sort_by_select = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//select[contains(@id, 'sortOne_top')]")
                )
            )
            sort_by_select.click()
            last_modified_option = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//option[@value='DD']"))
            )
            last_modified_option.click()
            time.sleep(5)
        except Exception as e:
            error_message = "No results found for this keyword."
            self.logger.error(f"{error_message} Error: {str(e).splitlines()[0]}")
            raise Exception(error_message)

    def get_urls(self, keyword: str, limited_page: int) -> Tuple[
        List[Tuple[str, str, str, str]], List[Tuple[str, str, str, str]]]:
        """
        Extracts PDF and non-PDF URLs from the search results based on the keyword.

        Args:
            keyword (str): The keyword used for searching.

        Returns:
            Tuple[List[Tuple[str, str, str, str]], List[Tuple[str, str, str, str]]]:
            Lists containing PDF URLs and non-PDF URLs with their metadata.
        """
        pdf_urls = []
        non_pdf_urls = []

        self.driver.get(self.base_url)
        time.sleep(5)

        try:
            self.search_for_keyword(keyword)
            self.sort_by_last_modified()
            self.current_page = 1
            while True:
                self.logger.info(f"Processing page {self.current_page}")
                search_results = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, "//div[@id='EurlexContent']//div[@class='SearchResult']")
                    )
                )

                pdf_urls.extend(self.extract_links(search_results, 'pdf'))
                non_pdf_urls.extend(self.extract_links(search_results, 'html'))

                if not self.click_next_button(limited_page):
                    break

        except Exception as e:
            self.log_error(e, self.driver.current_url)

        return pdf_urls, non_pdf_urls

    def extract_links(self, search_results, link_type: str) -> List[Tuple[str, str, str, str]]:
        """
        Extracts links of a specified type (PDF or HTML) from the search results.

        Args:
            search_results: Web elements containing the search results.
            link_type (str): The type of link to extract ('pdf' or 'html').

        Returns:
            List[Tuple[str, str, str, str]]:
            List of tuples containing (url, date, unique_name, description).
        """
        self.logger.info(f"Extracting {link_type} links from results.")
        urls = []
        for result in search_results:
            name_elements = result.find_elements(By.XPATH, ".//a[starts-with(@id, 'cellar_') and @href]")
            links = result.find_elements(By.XPATH, f".//a[starts-with(@title, '{link_type}') and @href]")
            dates = result.find_elements(By.XPATH, ".//dd[contains(text(), '/')]")

            for name_element, date, link in zip(name_elements, dates, links):
                name_text = name_element.text.strip()[:20]
                date_text = self.format_date(date.text.strip())
                day, month, year = date_text.split('-')
                date_text = f"{year}-{month}-{day}"

                url = link.get_attribute("href")
                description_text = name_element.text.strip()

                # Create a unique file name
                unique_name = f"{date_text}-{name_text}"
                unique_name = unique_name.replace('/', '_').replace(':', '').replace(' ', '_')

                # Ensure the name is unique
                counter = 1
                base_name = unique_name
                while any(unique_name in item for item in urls):
                    unique_name = f"{base_name}-{counter}"
                    counter += 1

                urls.append((url, date_text, unique_name, description_text))

        return urls

    def format_date(self, date_text: str) -> str:
        """
        Formats the date text by removing unwanted characters.

        Args:
            date_text (str): The original date text.

        Returns:
            str: The formatted date text.
        """
        if ";" in date_text:
            return date_text.split(';')[0].strip().replace('/', '-')
        return date_text.replace('/', '-')

    def click_next_button(self, limited_page: int) -> bool:
        """
        Clicks the 'Next' button to go to the next page of search results.

        Returns:
            bool: True if the next button was successfully clicked, False otherwise.
        """
        try:
            if limited_page == 0:
                limited_page = float('inf')

            if self.current_page < limited_page:
                self.current_page += 1
                next_button = self.driver.find_element(By.XPATH, "//div[@class='ResultsTools']//a[@title='Next Page']")
                if 'disabled' not in next_button.get_attribute('class') and next_button.get_attribute(
                        'href') != "javascript:;":
                    next_button.click()
                    time.sleep(5)
                    return True
        except Exception as e:
            self.logger.error(f"Error clicking next button: {e}")
        return False

    def download_pdf_files(self, urls: List[Tuple[str, str, str, str]]) -> List[dict]:
        """
        Downloads PDF files from the provided URLs.

        Args:
            urls (List[Tuple[str, str, str, str]]): List of URLs to download.

        Returns:
            List[dict]: List of dictionaries containing downloaded PDF data.
        """
        self.logger.info(f"Downloading PDF files.")
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
            except Exception as e:
                self.log_error(e, url)
        return data


    def process_non_pdf_urls(self, urls: List[Tuple[str, str, str, str]], keyword: str):
        """
        Processes non-PDF URLs by extracting summaries and checking for tables.

        Args:
            urls (List[Tuple[str, str, str, str]]): List of URLs to process.
            keyword (str): The keyword used to organize the saved files.
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

    def save_metadata(self, keyword: str, metadata: dict):
        """
        Saves the metadata of the page content to a JSON file.

        Args:
            keyword (str): The keyword used to organize the saved files.
            metadata (dict): The metadata to be saved.
        """
        self.logger.info(f"Saving metadata for: {metadata['name']}")
        metadata_folder = os.path.join('data/raw/eur_lex', keyword.replace(':', '').replace(' ', '_'), 'metadata')
        os.makedirs(metadata_folder, exist_ok=True)

        metadata_file_name = os.path.join(metadata_folder,
                                          f"metadata_{metadata['name']}.json")

        with open(metadata_file_name, 'w', encoding='utf-8') as metadata_file:
            json.dump(metadata, metadata_file, ensure_ascii=False, indent=4)
        self.logger.info(f"Metadata saved to {metadata_file_name}")

    def save_summary(self, keyword: str, url: str, date: str, name: str, description: str):
        """
        Saves the summary of the page content to a text file.

        Args:
            keyword (str): The keyword used to organize the saved files.
            url (str): The URL of the page.
            date (str): The date associated with the content.
            name (str): The name of the file.
            description (str): The description of the content.
        """
        self.logger.info(f"Saving summary for: {name}")
        keyword_folder = os.path.join('data/raw/eur_lex', keyword.replace(':', '').replace(' ', '_'), 'text')
        os.makedirs(keyword_folder, exist_ok=True)

        # Dosya ismini oluştururken tarih iki defa yazılmamasını sağla
        summary_file_name = os.path.join(keyword_folder, f"{name}.txt")

        with open(summary_file_name, 'w', encoding='utf-8') as summary_file:
            summary_file.write(f"Title: {name}\n")
            summary_file.write(f"Distribution date: {date}\n")
            summary_file.write(f"Keywords: {keyword}\n")
            summary_file.write(f"Summary: {description}\n")
        self.logger.info(f"Summary saved to {summary_file_name}")

    def save_pdf_data(self, keyword: str, data: List[dict]):
        """
        Saves the downloaded PDF data to files.

        Args:
            keyword (str): The keyword used to organize the saved files.
            data (List[dict]): The data to be saved.
        """
        self.logger.info(f"Saving PDF data for keyword: {keyword}")
        keyword_folder = os.path.join('data/raw/eur_lex', keyword.replace(':', '').replace(' ', '_'), 'pdf')
        os.makedirs(keyword_folder, exist_ok=True)

        for item in data:
            # Dosya ismini oluştururken tarih iki defa yazılmamasını sağla
            pdf_name = os.path.join(keyword_folder, f"{item['file_name']}.pdf")
            with open(pdf_name, 'wb') as pdf_file:
                pdf_file.write(item['content'])
            self.logger.info(f"PDF saved to {pdf_name}")

    def extract_and_save_tables(self, soup: BeautifulSoup, keyword: str, name: str, date: str):
        """
        Extracts tables from the HTML content and saves them in a JSON file.

        Args:
            soup (BeautifulSoup): The BeautifulSoup object containing the HTML content.
            keyword (str): The keyword used to organize the saved files.
            name (str): The name of the file.
            date (str): The date associated with the content.
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
            keyword_folder = os.path.join('data/raw/eur_lex', keyword.replace(':', '').replace(' ', '_'), 'json')
            os.makedirs(keyword_folder, exist_ok=True)

            # Dosya ismini oluştururken tarih iki defa yazılmamasını sağla
            table_file_name = os.path.join(keyword_folder, f"{name}.json")

            with open(table_file_name, 'w', encoding='utf-8') as table_file:
                json.dump(tables_data, table_file, ensure_ascii=False, indent=4)
            self.logger.info(f"Saved tables to {table_file_name}")

    def create_folder_structure(self, keyword: str):
        """
        Creates the folder structure for saving files related to the keyword.

        Args:
            keyword (str): The keyword used to organize the folder structure.
        """
        self.logger.info(f"Creating folder structure for keyword: {keyword}")
        keyword_folder = os.path.join('data/raw/eur_lex', keyword.replace(':', '').replace(' ', '_'))
        os.makedirs(keyword_folder, exist_ok=True)
        os.makedirs(os.path.join(keyword_folder, 'pdf'), exist_ok=True)
        os.makedirs(os.path.join(keyword_folder, 'text'), exist_ok=True)
        os.makedirs(os.path.join(keyword_folder, 'metadata'), exist_ok=True)
        os.makedirs(os.path.join(keyword_folder, 'json'), exist_ok=True)

    def log_error(self, error: Exception, url: str):
        """
        Logs an error encountered during the scraping process.

        Args:
            error (Exception): The exception encountered.
            url (str): The URL where the error occurred.
        """
        self.logger.error(f"Error at {url}: {str(error)}")