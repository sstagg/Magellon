import time
import pytermgui as ptg
import click as click
import npyscreen
from rich import print
from rich.progress import Progress
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
import textualize as tx
from rich.text import Text
from tqdm import tqdm
import pyfiglet as pyfiglet

import platform
import subprocess

print("[bold]Hello, Rich![/bold]")
print("[underline]This text is underlined.[/underline]")
print("[italic]This text is in italics.[/italic]")
print("[reverse]This text has a reversed background.[/reverse]")

print("[bold red]Error:[/bold red] Something went wrong.")
print("[blue]This text is blue.[/blue]")
print("[green]This text is green.[/green]")
print("[yellow on blue]This text is yellow on blue.[/yellow on blue]")

code = "def say_hello():\n    print('Hello, Rich!')"

print(Syntax(code, "python", theme="monokai", line_numbers=True))

table = Table(title="Student Grades")
table.add_column("Name", justify="right", style="cyan", no_wrap=True)
table.add_column("Subject", style="magenta")
table.add_column("Grade", style="green")

table.add_row("Alice", "Math", "A+")
table.add_row("Bob", "Science", "B")
table.add_row("Charlie", "English", "A")

print(table)

progress = Progress()

task = progress.add_task("[cyan]Processing...", total=100)

while not progress.finished:
    progress.update(task, advance=10)
    # Perform some work here

progress.stop()

items = range(10)  # Your iterable object

for item in tqdm(items, desc="Processing", unit="item"):
    print(item)

ascii_art = '''



+------------------------------------------------+
|                                                |
|                                                |
|                                                |
|                                                |
|                      +----------+              |
|                      | Magellon |              |
|                      +----------+              |
|                                                |
|                                                |
|                                                |
|                                                |
+------------------------------------------------+
'''
text = Text(ascii_art)
blue_style = Style(color="blue")
red_style = Style(color="red")
# # text.stylize( style=blue_style,start= 11, end=58)
# # text.stylize( style=red_style,start= 59, end=68)
print(text)


title = pyfiglet.figlet_format('Magellon', font='speed')
print(f'[magenta]{title}[/magenta]')








# @click.command()
# @click.option("--count", default=1, help="Number of greetings.")
# @click.option("--name", prompt="Your name", help="The person to greet.")
# def hello(count, name):
#     """Simple program that greets NAME for a total of COUNT times."""
#     for _ in range(count):
#         click.echo(f"Hello, {name}!")
#
#
# if __name__ == '__main__':
#     hello()


# class App(npyscreen.StandardApp):
#     def onStart(self):
#         self.addForm("MAIN", MainForm, name="Hello Medium!")
#
#
# class MainForm(npyscreen.ActionForm):
#     # Constructor
#     def create(self):
#         # Add the TitleText widget to the form
#         self.title = self.add(npyscreen.TitleText, name="TitleText", value="Hello World!")
#
#     # Override method that triggers when you click the "ok"
#     def on_ok(self):
#         self.parentApp.setNextForm(None)
#
#     # Override method that triggers when you click the "cancel"
#     def on_cancel(self):
#         self.title.value = "Hello World!"
#
#
# MyApp = App()
# MyApp.run()


# def macro_time(fmt: str) -> str:
#     return time.strftime(fmt)
#
#
# ptg.tim.define("!time", macro_time)
#
# with ptg.WindowManager() as manager:
#     manager.layout.add_slot("Body")
#     manager.add(
#         ptg.Window("[bold]The current time is:[/]\n\n[!time 75]%c", box="EMPTY")
#     )


# def install_ansible():
#     system = platform.system().lower()
#
#     if system == 'linux':
#         distro = platform.dist()[0].lower()
#         if distro == 'debian':
#             subprocess.call(['sudo', 'apt', 'update'])
#             subprocess.call(['sudo', 'apt', 'install', '-y', 'ansible'])
#         elif distro == 'centos':
#             subprocess.call(['sudo', 'yum', 'install', '-y', 'epel-release'])
#             subprocess.call(['sudo', 'yum', 'install', '-y', 'ansible'])
#         else:
#             print("Unsupported Linux distribution. Ansible installation is not supported.")
#     elif system == 'darwin':
#         subprocess.call(['brew', 'update'])
#         subprocess.call(['brew', 'install', 'ansible'])
#     elif system == 'windows':
#         subprocess.call(['pip', 'install', 'ansible'])
#     else:
#         print("Unsupported operating system. Ansible installation is not supported.")
#
# if __name__ == '__main__':
#     install_ansible()
