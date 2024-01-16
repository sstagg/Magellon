from rich import print
import pyfiglet as pyfiglet

def add_one(number):
    title = pyfiglet.figlet_format('Magellon', font='speed')
    print(f'[magenta]{title}[/magenta]')
    return number + 1