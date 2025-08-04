# assistant/io_adapter.py

from abc import ABC, abstractmethod

class IOAdapter(ABC):
    @abstractmethod
    def prompt(self, message: str) -> None:
        ...

    @abstractmethod
    def collect(self, prompt_text: str) -> str:
        ...

    @abstractmethod
    def confirm(self, message: str) -> None:
        ...

class CLIAdapter(IOAdapter):
    def prompt(self, message: str) -> None:
        print(message)

    def collect(self, prompt_text: str) -> str:
        return input(prompt_text).strip()

    def confirm(self, message: str) -> None:
        print(message)
