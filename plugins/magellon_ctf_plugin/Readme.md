# Welcome to Magellon
Welcome aboard! We appreciate your choice in Magellon for your plugin development endeavors. Magellon is a robust Python-based platform,
and each plugin is implemented as a FastAPI application. This README is designed to furnish you with a comprehensive guide on how to develop,
compile, run, test, and deploy plugins using the Magellon CLI.


## Getting Started

Before diving into the development process, ensure you have the following prerequisites installed:
1. Magellon CLI
2. Python 3.8 or later

## Setting Up Your Plugin

### Create a New Plugin
To initiate a new plugin, utilize the following command:
`magellon plugins create `
This command generates a basic Python project for your Magellon plugin. The project is created based on the information
provided in an init.json file, which contains essential details about your plugin. If you don't have this file, you can 
create it without passing any arguments. Subsequently, you can edit the file and rerun the command to generate a new project for your plugin.

### Navigate to Your Plugin Directory
`cd <plugin-name>`


### create a virtual environment
```
python3 -m venv venv

source env/bin/activate
or win: >.\env\Scripts\activate  and finally: >deactivate
```


### Install Dependencies

```
pip install -r requirements.txt
```
### Run

```
uvicorn main:app --host 0.0.0.0 --port 8181
python.exe -m uvicorn main:app --reload
```
http://127.0.0.1:8000/docs#/

http://127.0.0.1:8000/setup

### Run Docker
there is docker file Dockerfile in the current working directory
```
# Assuming there is a Dockerfile in the current working directory

# Build the Docker image from the current directory
docker build .

# Build the Docker image with a specified tag
docker build -t <yourname>/<plugin-name> .

sudo docker network create magellon

# Push the Docker image to a Docker registry (replace <yourname> with your Docker Hub username or another registry)
sudo docker push <yourname>/<plugin-name>

# Run the Docker container as a daemon (detached) with automatic restart, specifying network, ports, and volumes
sudo docker run -d --restart=always --name <yourname>/<plugin-name> --network magellon -p 8000:80 -v /magellon/data:/app/data -v /magellon/configs:/app/configs -v /gpfs:/gpfs -e DATA_DIR=/app/data khoshbin/magellon-main-service
sudo docker run -d --restart=always \
--name magellon-core-service01 \
--network magellon \
-p 8000:80 \
-v /magellon/data:/app/data \
-v /magellon/configs:/app/config \
-v /gpfs:/app/nfs \
-e DATA_DIR=/app/data \
khoshbin/magellon-main-service

# Run the Docker container interactively with a terminal, specifying network, ports, and volumes
sudo docker run -it --restart=always --name <yourname>/<plugin-name> --network magellon -p 8000:80 -v /magellon/data:/app/data -v /magellon/configs:/app/configs -v /gpfs:/gpfs -e DATA_DIR=/app/data khoshbin/magellon-main-service

# Remove a Docker container forcefully (replace magellon-core-service01 with your actual container name)
sudo docker rm -f magellon-core-service01

# Remove a Docker image forcefully (replace <yourname>/<plugin-name> with your actual image name)
sudo docker rmi -f <yourname>/<plugin-name>
```
### Development
Writing Your Plugin

Open the generated plugin files in your preferred code editor.
Customize the plugin code according to your requirements. Since each plugin is a FastAPI application, refer to the FastAPI documentation for guidance on building APIs.

Reading Configurations


Logging
Metrics
Getting tasks to do


### Deployment

`magellon plugins deploy`


### grafana
```
c1 = Gauge('root_request_counter_gauge', 'Number of Request')
s = Summary('root_request_latency_seconds', 'Description of summary')
s.observe(4.7)

i = Info('plugin', 'information about magellons plugin')
if plugin_info.description is not None:
i.info({'name': plugin_info.name, 'description': plugin_info.description, 'instance': plugin_info.instance_id})
else:
i.info({'name': plugin_info.name, 'description': 'No description', 'instance': plugin_info.instance_id})
c1.inc()



```
    # os.system("SETX {0} {1} /M".format("start", "test"))
    # os.environ["MY_VARIABLE"] = "some_value"
    # load_dotenv()
    # for key, value in os.environ.items():
    #     print(f"{key}: {value}")
    # Measure the duration of the / endpoint
    # with http_request_duration_histogram.labels(endpoint='/').time():
    #     logger.info("Executing root endpoint")
    #     c1.inc()
    # time.sleep(1)
    # logging.info("Executing root endpoint")



### elastic-apm
```
app = FastAPI(debug=False, title=f"Magellan {plugin_info.name}", description=plugin_info.description,
              version=plugin_info.version)

apm = make_apm_client({
    'SERVICE_NAME': 'magellon',
    'SECRET_TOKEN': 'aiietTiKcvOjbne0Zs',
    'SERVER_URL': 'https://ad0164bb13d948b89c94c175f1ce3151.apm.us-central1.gcp.cloud.es.io:443',
    'ENVIRONMENT': 'dev',
})

app.add_middleware(ElasticAPM, client=apm)

```

### rich

```
from rich.console import Console
from rich.table import Table

console = Console()
console.log("This is a [bold cyan]bold cyan[/bold cyan] message")
console.print("This is a [bold red]bold red[/bold red] message with a smiley :smiley:")

    table = Table(title="Example Table", show_header=True)
    table.add_column("Name")
    table.add_column("Age")

    table.add_row("John Doe", "30")
    table.add_row("Jane Smith", "25")

    console.print(table)
```



### Pydantic vs Python data classes
Pydantic and Python data classes are both used for defining data structures in a concise and readable manner, but they serve slightly different purposes and have different features. Let's explore the benefits of Pydantic models in comparison to Python data classes:
    Data Validation:
        Pydantic provides built-in data validation. When you define a Pydantic model, it automatically validates the input data against the specified data types and constraints. This ensures that the data adheres to the expected structure, reducing the chances of runtime errors.
    Data Parsing and Conversion:
        Pydantic can automatically parse and convert input data to the specified types. For example, if you define a field as an integer, Pydantic will attempt to convert a string representation of an integer to an actual integer.
    Default Values and Optional Fields:
        Pydantic allows you to define default values for fields, making it easy to handle optional or missing data. This is particularly useful when working with external data sources that may not always provide all the required information.
    Documentation and IDE Support:
        Pydantic models include type information and metadata, making them more informative and easier to document. This can enhance code readability and provide better support for code editors and IDEs, helping with auto-completion and type checking.
    JSON Schema Generation:
        Pydantic can automatically generate JSON Schema from your model definitions. This is useful for documenting and validating the expected structure of JSON data, especially in web applications where APIs are commonly used.
    Integration with ORM Systems:
        Pydantic integrates well with ORM (Object-Relational Mapping) systems like SQLAlchemy. You can use Pydantic models to define the data structure and validation rules, and then easily convert between Pydantic models and ORM models.
    Configurable Validation and Parsing:
        Pydantic allows you to customize the validation and parsing behavior by using configurable settings. This flexibility can be helpful in adapting the library to different use cases and project requirements.
    Cross-Field Validation:
        Pydantic supports cross-field validation, meaning you can define validation rules that involve multiple fields. This is beneficial when you need to enforce constraints that depend on the values of multiple attributes.
While Python data classes are suitable for defining simple data structures, Pydantic is specifically designed for data validation, parsing, and conversion, making it a powerful choice when dealing with complex input data in applications such as web APIs or data processing pipelines


### Additional Resources

    Magellon Documentation
    Magellon API Reference

https://www.elastic.co/guide/en/elasticsearch/reference/8.11/getting-started.html
https://www.elastic.co/guide/en/elasticsearch/reference/current/docker.html

### Support

If you encounter any issues or have questions, feel free to reach out to the Magellon community or open an issue on the GitHub repository.

Happy coding! 🚀