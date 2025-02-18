from abc import ABC, abstractmethod
import logging

class BaseEventParser:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def parse_events(self, response):
        pass