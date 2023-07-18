import os

import pyfiglet
from rich import print

import ansible_runner

import rich.traceback

rich.traceback.install(show_locals=True)

title = pyfiglet.figlet_format('Magellon Test', font='speed')
print(f'[magenta]{title}[/magenta]')


def run_playbook():
    # env = Environment('<!--', '-->', '${', '}', '<!--#', '-->')
    # installing the required packages
    try:
        with open('playbook.yml', 'r') as file:
            playbook_template = (file.read())
        with open('inventory.ini', 'r') as file:
            inventory_template = (file.read())

        # text_log.write(runner_result.stats)
        runner = ansible_runner.run_async(private_data_dir='.', inventory=inventory_template,
                                          playbook=playbook_template)

        # Print progress information as it becomes available
        while runner.is_alive():
            event = runner.events.get()
            if event:
                if event['event'] == 'runner_on_ok':
                    # Display progress for tasks that completed successfully
                    print(f"Task '{event['event_data']['task_name']}' completed successfully")
                elif event['event'] == 'runner_on_failed':
                    # Display progress for failed tasks
                    print(f"Task '{event['event_data']['task_name']}' failed")
                # Add more conditions for other events as needed
                else:
                    # Display progress for other events
                    print(event)

        # Wait for the playbook run to complete
        runner.wait()

        # Print the final playbook results
        print(runner.get_results())


    except Exception as e:
        print(e.__str__())


run_playbook()
