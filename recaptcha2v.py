
import io
import random
import time
import requests

# Speech Recognition Imports
import speech_recognition as sr
from pydub import AudioSegment

# Selenium
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

# Stem
from stem import Signal
from stem.control import Controller
from stem.process import *


# Randomization Related
MIN_RAND = 0.64
MAX_RAND = 1.27
LONG_MIN_RAND = 4.78
LONG_MAX_RAND = 11.1

# from https://www.houndify.com/ free account
HOUNDIFY_CLIENT_ID = 'ID'
HOUNDIFY_CLIENT_KEY = 'KEY'

# TOR process parameters
TOR_SOCKS = '9150'
TOR_CTRL = '9151'

# Training loop
NUMBER_OF_ITERATIONS = 5
RECAPTCHA_PAGE_URL = 'https://www.google.com/recaptcha/api2/demo'


class ReCaptcha(object):
    def __init__(self):

        # Configure Firefox browser to use TOR
        def proxy(proxy_host, proxy_port):
            fp = webdriver.FirefoxProfile()
            # Direct = 0, Manual = 1, PAC = 2, AUTODETECT = 4, SYSTEM = 5
            fp.set_preference('network.proxy.type', 1)
            fp.set_preference('network.proxy.socks', proxy_host)
            fp.set_preference('network.proxy.socks_port', int(proxy_port))
            fp.set_preference('dom.webdriver.enabled', False)
            fp.set_preference('useAutomationExtension', False)
            fp.update_preferences()
            options = Options()
            return webdriver.Firefox(options=options, firefox_profile=fp)

        self.driver = proxy('127.0.0.1', TOR_SOCKS)

    # Choose new Tor Circuit for this Site (new IP)
    def switch_ip(self):
        with Controller.from_port(port=int(TOR_CTRL)) as controller:
            controller.authenticate()
            controller.signal(Signal.NEWNYM)
            print('[{0}] New Tor Circuit for this Site'.format(self.current_iteration))

    def is_exists_by_xpath(self, xpath):
        try:
            self.driver.find_element_by_xpath(xpath)
        except NoSuchElementException:
            return False
        return True

    def get_recaptcha_challenge(self):
        while True:
            # Navigate to a ReCaptcha page
            self.driver.get(RECAPTCHA_PAGE_URL)
            time.sleep(random.uniform(MIN_RAND, MAX_RAND))

            # Get all the iframes on the page
            iframes = self.driver.find_elements_by_tag_name("iframe")

            # Switch focus to ReCaptcha iframe
            self.driver.switch_to.frame(iframes[0])
            time.sleep(random.uniform(MIN_RAND, MAX_RAND))

            # Verify ReCaptcha checkbox is present
            if not self.is_exists_by_xpath('//div[@class="recaptcha-checkbox-checkmark" and @role="presentation"]'):
                print("[{0}] No element in the frame!".format(self.current_iteration))
                continue

            # Click on ReCaptcha checkbox
            self.driver.find_element_by_xpath(
                '//div[@class="recaptcha-checkbox-border" and @role="presentation"]').click()
            time.sleep(random.uniform(LONG_MIN_RAND, LONG_MAX_RAND))

            # Check if the ReCaptcha has no challenge
            if self.is_exists_by_xpath('//span[@aria-checked="true"]'):
                print("[{0}] ReCaptcha has no challenge. Trying again!".format(self.current_iteration))
            else:
                return

    def get_audio_challenge(self, iframes):
        # Switch to the last iframe (the new one)
        self.driver.switch_to.frame(iframes[-1])

        # Check if the audio challenge button is present
        if not self.is_exists_by_xpath('//button[@id="recaptcha-audio-button"]'):
            print("[{0}] No element of audio challenge!".format(self.current_iteration))
            return False

        print("[{0}] Choose an audio challenge".format(self.current_iteration))
        # Click on the audio challenge button
        self.driver.find_element_by_xpath('//button[@id="recaptcha-audio-button"]').click()
        time.sleep(random.uniform(LONG_MIN_RAND, LONG_MAX_RAND))

    def get_challenge_audio(self, url):
        # Download the challenge audio and store in memory
        request = requests.get(url)
        audio_file = io.BytesIO(request.content)

        # Convert the audio to a compatible format in memory
        converted_audio = io.BytesIO()
        sound = AudioSegment.from_mp3(audio_file)
        sound.export(converted_audio, format="wav")
        converted_audio.seek(0)

        return converted_audio

    def speech_to_text(self, audio_source):
        # Initialize a new recognizer with the audio in memory as source
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_source) as source:
            audio = recognizer.record(source)  # read the entire audio file

        # recognize speech using Google Speech Recognition
        try:
            audio_output = recognizer.recognize_google(audio)
            print("[{0}] Google Speech Recognition: ".format(self.current_iteration) + audio_output)

            # Check if we got harder audio captcha
            if any(character.isdigit() or character.isupper() for character in audio_output):
                # Use Houndify to detect the harder audio captcha
                audio_output = recognizer.recognize_houndify(
                    audio, client_id=HOUNDIFY_CLIENT_ID, client_key=HOUNDIFY_CLIENT_KEY)
                print("[{0}] Houndify Speech to Text: ".format(self.current_iteration) + audio_output)

        except sr.UnknownValueError or sr.RequestError:
            print("[{0}] Google Speech Recognition could not understand audio".format(self.current_iteration))
            audio_output = recognizer.recognize_houndify(
                audio, client_id=HOUNDIFY_CLIENT_ID, client_key=HOUNDIFY_CLIENT_KEY)
            print("[{0}] Houndify Speech to Text:: ".format(self.current_iteration) + audio_output)

        return audio_output

    def solve_audio_challenge(self):
        # Verify audio challenge download button is present
        if not self.is_exists_by_xpath('//*[@id="audio-source"]'):
            print("[{0}] No element in audio challenge download link!".format(self.current_iteration))
            return False

        # If text challenge - reload the challenge
        while self.is_exists_by_xpath('//div[@class="rc-text-challenge"]'):
            print("[{0}] Got a text challenge! Reloading!".format(self.current_iteration))
            self.driver.find_element_by_id('recaptcha-reload-button').click()
            time.sleep(random.uniform(MIN_RAND, MAX_RAND))

        # Get the audio challenge URI from the download link
        download_object = self.driver.find_element_by_xpath('//*[@id="audio-source"]')
        download_link = download_object.get_attribute('src')

        # Get the challenge audio to send to Google
        converted_audio = self.get_challenge_audio(download_link)

        # Send the audio to Google Speech Recognition API and get the output
        audio_output = self.speech_to_text(converted_audio)

        # Enter the audio challenge solution
        self.driver.find_element_by_id('audio-response').send_keys(audio_output)
        time.sleep(random.uniform(LONG_MIN_RAND, LONG_MAX_RAND))

        # Click on verify
        self.driver.find_element_by_id('recaptcha-verify-button').click()
        time.sleep(random.uniform(LONG_MIN_RAND, LONG_MAX_RAND))

        return True

    def solve(self, current_iteration):
        self.current_iteration = current_iteration + 1

        # Get a ReCaptcha Challenge
        self.get_recaptcha_challenge()

        # Switch to page's main frame
        self.driver.switch_to.default_content()

        # Get all the iframes on the page again, there is a new one with a challenge
        iframes = self.driver.find_elements_by_tag_name("iframe")

        # Get audio challenge
        self.get_audio_challenge(iframes)

        # Solve the audio challenge
        if not self.solve_audio_challenge():
            return False

        # Check if there is another audio challenge and solve it too
        if self.is_exists_by_xpath('//div[contains(text(), "Multiple correct solutions required")]') \
                and self.is_exists_by_xpath('//div[@class="rc-audiochallenge-error-message"]'):
            print("[{0}] Multiple correct solutions required!".format(self.current_iteration))
            self.solve_audio_challenge()
            time.sleep(random.uniform(LONG_MIN_RAND, LONG_MAX_RAND))

        # Switch to the reCaptcha iframe to verify it is solved
        self.driver.switch_to.default_content()
        self.driver.switch_to.frame(iframes[0])

        # New Tor Circuit for this Site
        self.switch_ip()

        return self.is_exists_by_xpath('//span[@aria-checked="true"]')


def main():
    # Use TOR for keep you on the safe side
    tor_process = stem.process.launch_tor_with_config(
        config={'SOCKSPort': TOR_SOCKS, 'ControlPort': TOR_CTRL})

    recaptcha2v = ReCaptcha()
    counter = 0

    for i in range(NUMBER_OF_ITERATIONS):
        if recaptcha2v.solve(i):
            counter += 1

        time.sleep(random.uniform(LONG_MIN_RAND, LONG_MAX_RAND))
        print("Successful breaks: {0}".format(counter))

    print("Total successful breaks: {0}/{1}".format(counter, NUMBER_OF_ITERATIONS))

    # Clean it up
    tor_process.kill()
    recaptcha2v.driver.close()


if __name__ == '__main__':
    main()
