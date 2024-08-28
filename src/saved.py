import os
from src.bots import EchaWebScraper, EurWebScraper, ResmiWebScraper
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


class ScriptRunner:

    def __init__(self, script_keywords_file):
        """
        Initialize the ScriptRunner.

        Parameters:
        script_keywords_file (str): Path to the text file containing script names,
                                    links, and associated keywords.
        """
        self.script_keywords_file = script_keywords_file
        self.executed_entries = self.load_executed_entries()


    def load_executed_entries(self):
        """
        Load the executed entries from the file into a dictionary.

        Returns:
        dict: A dictionary where the keys are tuples of (script name, link)
              and the values are sets of executed keywords.
        """
        executed_entries = {}
        if os.path.exists(self.script_keywords_file):
            with open(self.script_keywords_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if ' Keywords: ' in line:
                        script_and_link, keywords_str = line.split(' Keywords: ')
                        parts = script_and_link.split(' ')
                        script = parts[0].strip()
                        link = ' '.join(parts[1:]).strip()
                        keywords = set(keywords_str.strip().split(', '))
                        executed_entries[(script, link)] = keywords
        return executed_entries

    def save_executed_entries(self):
        """
        Save the executed entries back to the text file,
        ensuring that the file reflects the current state of executed scripts and keywords.
        """
        with open(self.script_keywords_file, 'w') as f:
            for (script, link), keywords in self.executed_entries.items():
                keywords_str = ', '.join(keywords)
                f.write(f'{script} {link} Keywords: {keywords_str}\n')

    def read_scripts_from_file(self, filepath):
        """
        Read scripts information from a text file with the specified format.

        Parameters:
        filepath (str): Path to the text file containing scripts information.

        Returns:
        list: A list of tuples where each tuple contains:
              (script name, link, list of keywords, limited page number).
        """
        scripts = []
        current_script = None
        keywords = []

        with open(filepath, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        for line in lines:
            line = line.strip()
            if line.startswith("Name:"):
                if current_script:  # Önceki script bilgilerini ekle
                    scripts.append((current_script[0], current_script[1], keywords, current_script[2]))
                script_name = line.split("Name:")[1].strip()
                current_script = [script_name, None, None]
                keywords = []
            elif line.startswith("Link:"):
                current_script[1] = line.split("Link:")[1].strip()
            elif line.startswith("Limited page number:"):
                current_script[2] = int(line.split("Limited page number:")[1].strip())
            elif line.startswith("Keywords:"):
                continue  # Anahtar kelimeler bu satırdan sonra gelecek
            elif line:  # Anahtar kelimeler bu durumda eklenir
                keywords.append(line)

        # Son script'i ekle
        if current_script:
            scripts.append((current_script[0], current_script[1], keywords, current_script[2]))

        return scripts

    def run_scripts(self, scripts):
        """
        Run the given scripts with their respective links and keywords.

        Parameters:
        scripts (list): A list of tuples where each tuple contains:
                        (script name, link, list of keywords, limited page number).
        """
        for script, link, keywords, limited_page in scripts:
            key = (script, link)
            new_keywords = set(keywords)
            executed_keywords = self.executed_entries.get(key, set())

            keywords_to_run = new_keywords - executed_keywords
            if keywords_to_run:
                self.run_script(script, link, list(keywords_to_run), limited_page)
                executed_keywords.update(keywords_to_run)
                self.executed_entries[key] = executed_keywords
                self.save_executed_entries()
            else:
                print(f'Skipping {script} with link {link} (all keywords already executed)')

    def run_script(self, script, link, keywords, limited_page):
        """
        Run the specified script with the provided link and keywords.

        Parameters:
        script (str): The name of the script to run.
        link (str): The base URL or link to be used in the script.
        keywords (list): A list of keywords to process with the script.
        limited_page (int): The page limit for scraping (if applicable).
        """


        for keyword in keywords:

            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_argument("--window-size=1920,1080")

            driver = webdriver.Chrome(options=chrome_options)

            print(f'Running {script} with link {link} and keyword: {keyword}')

            if script == 'echaWebScraping.py':
                scraper = EchaWebScraper(key_words=[keyword], base_url=link, limited_page=limited_page, driver=driver)
                scraper.start()
            elif script == 'eur_lexWebScraping.py':
                scraper = EurWebScraper(key_words=[keyword], base_url=link, limited_page=limited_page, driver=driver)
                scraper.start()
            elif script == 'resmiWebScraping.py':
                scraper = ResmiWebScraper(key_words=[keyword], base_url=link, limited_page=limited_page, driver=driver)
                scraper.start()

            # Update the executed keywords
            if (script, link) not in self.executed_entries:
                self.executed_entries[(script, link)] = set()

            self.executed_entries[(script, link)].add(keyword)
            self.save_executed_entries()