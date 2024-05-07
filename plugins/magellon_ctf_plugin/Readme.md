# Welcome to Magellon
Welcome aboard! We appreciate your choice in Magellon for your plugin development endeavors. Magellon is a robust Python-based platform,
and each plugin is implemented as a FastAPI application. This README is designed to furnish you with a comprehensive guide on how to develop,
compile, run, test, and deploy plugins using the Magellon CLI.


## Getting Started

Before diving into the development process, ensure you have the following prerequisites installed:
1. Magellon CLI
2. Python 3.8 or later

ldd /app/ctffind
apt-key adv --fetch-keys http://repos.codelite.org/CodeLite.asc
apt-add-repository 'deb http://repos.codelite.org/wx3.0.5/debian/ buster libs'
apt-add-repository 'deb http://ftp.de.debian.org/debian buster main'
apt-get install libwxbase3.0-0-unofficial \
libwxbase3.0-dev \
libwxgtk3.0-0-unofficial \
libwxgtk3.0-dev \
wx3.0-headers \
wx-common \
libwxbase3.0-dbg \
libwxgtk3.0-dbg \
wx3.0-i18n \
wx3.0-examples \
wx3.0-doc

echo -e "/gpfs/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc output.mrc 1.0 300.0 2.7 0.07 512 30.0 5.0 5000.0 50000.0 100.0 no no no no no" | /app/ctffind

uname -m
x86_64 or amd64: This indicates a 64-bit Intel or AMD processor.

apt-file search libwx_baseu-3.0.so.0
apt-get install libwxbase3.0-0v5 libtiff5 libfftw3-single3
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

docker run -d \
-p 80:80 \
-v /path/to/your/data:/app/data \
-v /path/to/your/configs:/configs \
--env APP_ENV=production  # Or APP_ENV=development for development mode
magellon-ctf-plugin


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











The below is the example command to run the latest version of ctffind
# echo -e "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc\ndiagnostic_output.mrc\n1.0\n300.0\n2.70\n0.07\n512\n30.0\n5.0\n5000.0\n50000.0\n100.0\nno\nno\nno\nno\nno\nno\n" | ./ctffind


Input
{
"inputFile": "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc",
"outputFile" :"ouput.mrc",
"pixelSize": "1.0",
"sphericalAberration": 2.70,
"accelerationVoltage":  300.0,
"amplitudeContrast": 0.07,
"sizeOfAmplitudeSpectrum": 512,
"minimumResolution":30.0,
"maximumResolution":5.0,
"minimumDefocus":5000.0,
"maximumDefocus":50000.0,
"defocusSearchStep":100.0,
<!-- "isastigmatismPresent": false,
"slowerExhaustiveSearch": false,
"restraintOnAstogmatism": false,
"FindAdditionalPhaseShift": false,
"setExpertOptions":false -->
}

Steps to run the project:(Runs on only linux)
1) Clone the repository
   git clone "https://github.com/MDPuneethReddy/ctf.git"

2) Go to the project folder
   cd ctf

3) Create python virtual environment.
   python3 -m venv myenv

4) activate virtual environment.
   source myenv/bin/activate

5) Install the dependencies
   pip install -r requirements.txt

6) Create .env file.
   Next create a new file in the root directory called ".env" and copy the contents from ".env.dev".

7) Add CTF estimation compiled file and change it in .env

Then Add the CTF evaluation compiled file in the root directory and change the name of the env variable  "CTF_ESTIMATION_FILE" with the CTF evaluation file name.

8) Add sample input MRC file:
   Add Input MRC file in the root directory of the project. the sample mrc file is "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc"

9) Run the fastapi application

To Execute initially run the fastapi application using command "uvicorn main:app --reload" if you want to specify certain port "uvicorn main:app --reload --port 8001".

10) Execute the endpoint.
    Next using postman or swagger interface you can use "/execute" method to run the ctf. In the body of the execute method pass the input. the input json is mentioned above.

11) Expected result(Sample):
    {
    "data": {
    "status_code": 200,
    "message": "ctf completed successfully",
    "output_txt": "# Output from CTFFind version 4.1.14, run on 2024-03-05 10:08:51\n# Input file: 23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc ; Number of micrographs: 1\n# Pixel size: 1.000 Angstroms ; acceleration voltage: 300.0 keV ; spherical aberration: 2.70 mm ; amplitude contrast: 0.07\n# Box size: 512 pixels ; min. res.: 30.0 Angstroms ; max. res.: 5.0 Angstroms ; min. def.: 5000.0 um; max. def. 50000.0 um\n# Columns: #1 - micrograph number; #2 - defocus 1 [Angstroms]; #3 - defocus 2; #4 - azimuth of astigmatism; #5 - additional phase shift [radians]; #6 - cross correlation; #7 - spacing (in Angstroms) up to which CTF rings were fit successfully\n1.000000 10588.083984 9956.687500 -44.710212 0.000000 0.494779 4.102857\n",
    "output_avrot": "# Output from CTFFind version 4.1.14, run on 2024-03-05 10:08:53\n# Input file: 23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc ; Number of micrographs: 1\n# Pixel size: 1.000 Angstroms ; acceleration voltage: 300.0 keV ; spherical aberration: 2.70 mm ; amplitude contrast: 0.07\n# Box size: 512 pixels ; min. res.: 30.0 Angstroms ; max. res.: 5.0 Angstroms ; min. def.: 5000.0 um; max. def. 50000.0 um; num. frames averaged: 1\n# 6 lines per micrograph: #1 - spatial frequency (1/Angstroms); #2 - 1D rotational average of spectrum (assuming no astigmatism); #3 - 1D rotational average of spectrum; #4 - CTF fit; #5 - cross-correlation between spectrum and CTF fit; #6 - 2sigma of expected cross correlation of noise\n0.000000 0.001393 0.002786 0.004178 0.005571 0.006964 0.008357 0.009749 0.011142 0.012535 0.013928 0.015320 0.016713 0.018106 0.019499 0.020891 0.022284 0.023677 0.025070 0.026462 0.027855 0.029248 0.030641 0.032033 0.033426 0.034819 0.036212 0.037604 0.038997 0.040390 0.041783 0.043175 0.044568 0.045961 0.047354 0.048747 0.050139 0.051532 0.052925 0.054318 0.055710 0.057103 0.058496 0.059889 0.061281 0.062674 0.064067 0.065460 0.066852 0.068245 0.069638 0.071031 0.072423 0.073816 0.075209 0.076602 0.077994 0.079387 0.080780 0.082173 0.083565 0.084958 0.086351 0.087744 0.089136 0.090529 0.091922 0.093315 0.094708 0.096100 0.097493 0.098886 0.100279 0.101671 0.103064 0.104457 0.105850 0.107242 0.108635 0.110028 0.111421 0.112813 0.114206 0.115599 0.116992 0.118384 0.119777 0.121170 0.122563 0.123955 0.125348 0.126741 0.128134 0.129526 0.130919 0.132312 0.133705 0.135097 0.136490 0.137883 0.139276 0.140669 0.142061 0.143454 0.144847 0.146240 0.147632 0.149025 0.150418 0.151811 0.153203 0.154596 0.155989 0.157382 0.158774 0.160167 0.161560 0.162953 0.164345 0.165738 0.167131 0.168524 0.169916 0.171309 0.172702 0.174095 0.175487 0.176880 0.178273 0.179666 0.181058 0.182451 0.183844 0.185237 0.186630 0.188022 0.189415 0.190808 0.192201 0.193593 0.194986 0.196379 0.197772 0.199164 0.200557 0.201950 0.203343 0.204735 0.206128 0.207521 0.208914 0.210306 0.211699 0.213092 0.214485 0.215877 0.217270 0.218663 0.220056 0.221448 0.222841 0.224234 0.225627 0.227019 0.228412 0.229805 0.231198 0.232591 0.233983 0.235376 0.236769 0.238162 0.239554 0.240947 0.242340 0.243733 0.245125 0.246518 0.247911 0.249304 0.250696 0.252089 0.253482 0.254875 0.256267 0.257660 0.259053 0.260446 0.261838 0.263231 0.264624 0.266017 0.267409 0.268802 0.270195 0.271588 0.272981 0.274373 0.275766 0.277159 0.278552 0.279944 0.281337 0.282730 0.284123 0.285515 0.286908 0.288301 0.289694 0.291086 0.292479 0.293872 0.295265 0.296657 0.298050 0.299443 0.300836 0.302228 0.303621 0.305014 0.306407 0.307799 0.309192 0.310585 0.311978 0.313370 0.314763 0.316156 0.317549 0.318942 0.320334 0.321727 0.323120 0.324513 0.325905 0.327298 0.328691 0.330084 0.331476 0.332869 0.334262 0.335655 0.337047 0.338440 0.339833 0.341226 0.342618 0.344011 0.345404 0.346797 0.348189 0.349582 0.350975 0.352368 0.353760 0.355153 0.356546 0.357939 0.359331 0.360724 0.362117 0.363510 0.364903 0.366295 0.367688 0.369081 0.370474 0.371866 0.373259 0.374652 0.376045 0.377437 0.378830 0.380223 0.381616 0.383008 0.384401 0.385794 0.387187 0.388579 0.389972 0.391365 0.392758 0.394150 0.395543 0.396936 0.398329 0.399721 0.401114 0.402507 0.403900 0.405292 0.406685 0.408078 0.409471 0.410864 0.412256 0.413649 0.415042 0.416435 0.417827 0.419220 0.420613 0.422006 0.423398 0.424791 0.426184 0.427577 0.428969 0.430362 0.431755 0.433148 0.434540 0.435933 0.437326 0.438719 0.440111 0.441504 0.442897 0.444290 0.445682 0.447075 0.448468 0.449861 0.451253 0.452646 0.454039 0.455432 0.456825 0.458217 0.459610 0.461003 0.462396 0.463788 0.465181 0.466574 0.467967 0.469359 0.470752 0.472145 0.473538 0.474930 0.476323 0.477716 0.479109 0.480501 0.481894 0.483287 0.484680 0.486072 0.487465 0.488858 0.490251 0.491643 0.493036 0.494429 0.495822 0.497214 0.498607 0.500000 0.501393 0.502786 0.504178\n       0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.02354        0.03211        1.43211        2.09334        2.14577        2.11817        2.65154        2.53810        2.83298        2.77643        2.71326        2.45783        2.00089        1.93530        1.64460        1.34045        1.10610        0.72344        0.36965       -0.10615       -0.67260       -1.20370       -1.83959       -2.28117       -2.67719       -2.92407       -3.16335       -3.17262       -3.07459       -2.83616       -2.40179       -1.80344       -1.27176       -0.61652       -0.00881        0.56687        1.05757        1.45627        1.56152        1.71648        1.65033        1.49442        1.25464        0.89089        0.36544       -0.23441       -0.65861       -1.07779       -1.39695       -1.49812       -1.44904       -1.14813       -0.73752       -0.35501        0.16309        0.60022        0.93434        1.06101        1.11859        1.08538        0.72281        0.31644       -0.07110       -0.49918       -0.74913       -0.93683       -0.98477       -0.71100       -0.33304        0.05893        0.44135        0.73942        0.88453        0.87713        0.60117        0.31604       -0.00049       -0.34509       -0.55971       -0.61847       -0.48611       -0.24619       -0.02260        0.20604        0.39711        0.52716        0.43979        0.24747       -0.02929       -0.26207       -0.35948       -0.41718       -0.29575       -0.13953        0.07116        0.25291        0.35070        0.30371        0.16190       -0.02900       -0.16435       -0.25308       -0.22843       -0.18914       -0.00853        0.07446        0.15444        0.19458        0.10563        0.02717       -0.08302       -0.14378       -0.13357       -0.04817        0.03417        0.14628        0.18780        0.09475        0.04936       -0.02126       -0.09036       -0.08776       -0.05435       -0.01139        0.07845        0.09156        0.05408        0.04532       -0.00800       -0.06896       -0.06744        0.03570        0.05326        0.05796        0.06070        0.03267       -0.00378       -0.05081       -0.01368        0.02714        0.06458        0.07122        0.04596        0.03023        0.00206       -0.01724       -0.00808        0.01763        0.09338        0.04390       -0.00202       -0.02855       -0.04694        0.00127        0.02714        0.05658        0.05797        0.01624       -0.02689       -0.01474        0.01815        0.00412        0.07837        0.07611        0.04988       -0.00712       -0.02998        0.00464        0.08470        0.05713        0.03675        0.00806       -0.06150       -0.03365        0.02356        0.06651        0.07058        0.05232       -0.00092       -0.03327        0.03527        0.06259        0.06982        0.04603        0.00694       -0.02208       -0.01912        0.04917        0.09829        0.08799        0.00008       -0.02622        0.01244        0.06301        0.06797        0.06471        0.00107       -0.04200        0.01506        0.03436        0.06136        0.02466       -0.00000       -0.04194        0.02803        0.04646        0.06701        0.01556       -0.03453       -0.00950        0.02139        0.05095        0.04217        0.04945       -0.00409        0.01754        0.06005        0.04917        0.00470       -0.00985        0.03111        0.03995        0.03964        0.01238       -0.00209        0.01502        0.06717        0.02983        0.01723        0.02038       -0.01919        0.01965        0.03077        0.02199        0.03455       -0.00201        0.00857        0.02560        0.04016       -0.01271        0.01054        0.03687        0.08259        0.07116        0.00424        0.02462        0.01808        0.06190        0.03644       -0.02317        0.00369        0.01107        0.03018        0.03820       -0.01159        0.02663        0.05846        0.01789       -0.00194        0.02337        0.01972        0.06186        0.00089        0.03589        0.01541        0.01181        0.05329        0.03804        0.01345        0.02686        0.03255        0.01021       -0.02408       -0.00191        0.01254        0.01860       -0.00786        0.01724        0.03062        0.05283        0.07280       -0.01493       -0.02566        0.06751        0.01494        0.00575        0.04253        0.02459       -0.00387        0.00502        0.03744        0.04261       -0.00255        0.05043       -0.03962       -0.03096       -0.00094        0.06393        0.03466        0.09961        0.11048        0.03145       -0.04318        0.04623        0.00265        0.01417       -0.00218        0.09420        0.02941        0.10317        0.02227        0.02200       -0.00310       -0.05594       -0.03032        0.00595       -0.01354       -0.05266        0.03905       -0.00963        0.01733       -0.02653        0.00962        0.02589        0.08251        0.15902       -0.08117        0.00399        0.09424       -0.02887        0.09764       -0.09359        0.09871        0.09935        0.01511       -0.03293        0.05585       -0.11345        0.03335       -0.69249       -1.70876\n1.903040 1.874753 1.846689 1.818847 1.791227 1.763830 1.736655 1.709702 1.682971 1.656463 1.630176 1.604112 1.578271 1.552651 1.527254 1.502079 1.477127 1.452397 1.427889 1.403603 1.382156 1.364522 1.347413 1.439513 1.564611 1.660166 1.714932 1.761721 1.784176 1.803778 1.814301 1.800716 1.755711 1.690413 1.614863 1.529080 1.440573 1.349030 1.272016 1.180049 1.067660 0.930523 0.786791 0.632872 0.468618 0.316179 0.201153 0.105536 0.031914 -0.011838 -0.019976 0.006920 0.078971 0.174724 0.298015 0.449431 0.580256 0.725516 0.833050 0.928188 0.983019 0.981007 0.985585 0.954085 0.884973 0.811195 0.675796 0.520981 0.371499 0.243539 0.146353 0.074559 0.043507 0.062733 0.145969 0.237951 0.338850 0.433182 0.560238 0.607053 0.624171 0.608886 0.578885 0.471603 0.357361 0.241846 0.131066 0.039388 -0.004122 0.009498 0.058408 0.153127 0.254716 0.352952 0.433785 0.449699 0.414665 0.355197 0.280843 0.185701 0.069839 0.007766 -0.026943 -0.002011 0.069008 0.146500 0.209401 0.256422 0.300502 0.282717 0.234792 0.152021 0.059068 0.027776 0.001152 0.009920 0.070525 0.138848 0.193904 0.215217 0.209848 0.177942 0.112358 0.073074 0.023199 0.008571 0.015046 0.063279 0.104203 0.146157 0.128178 0.129888 0.103176 0.064191 0.021639 -0.007819 0.015237 0.055814 0.083385 0.118687 0.127602 0.103714 0.069285 0.028141 0.002489 -0.008261 0.015818 0.058850 0.083282 0.092304 0.083904 0.053334 0.019615 -0.007269 0.014296 0.017402 0.051854 0.073471 0.054808 0.047081 0.011398 -0.013078 -0.003839 0.007004 0.034678 0.046574 0.075210 0.024008 0.013539 -0.008285 -0.017937 -0.010664 0.035125 0.033383 0.037079 0.023474 0.004639 -0.021866 -0.021726 0.013285 0.029136 0.052118 0.035462 0.005297 -0.016726 -0.029715 0.000971 0.037492 0.037772 0.048661 0.022164 -0.013297 -0.013067 -0.009086 0.021187 0.034904 0.034452 0.006976 -0.034411 -0.016019 -0.005148 0.033960 0.032789 0.015412 -0.007375 -0.018919 -0.038750 0.009438 0.019642 0.011026 -0.008936 -0.018957 -0.025543 -0.012274 -0.000789 0.015589 0.001100 -0.036904 -0.043673 -0.037617 -0.016036 -0.001895 -0.015310 -0.040421 -0.042125 -0.030686 -0.015621 -0.000416 -0.016066 -0.035205 -0.031433 -0.036379 0.000933 0.000429 -0.008259 -0.031714 -0.037024 -0.018599 -0.002492 0.005157 -0.021126 -0.022991 -0.034152 -0.003861 -0.002731 -0.002967 -0.004274 -0.018155 -0.018946 0.005271 0.010217 -0.004285 -0.022228 -0.018672 0.004771 0.014699 0.008619 -0.002874 0.000258 -0.006095 -0.000846 0.011057 0.003950 0.016473 -0.015382 0.005878 0.006388 0.014516 -0.020990 -0.016897 0.008416 0.012550 0.003674 -0.014491 0.006151 0.016047 0.000572 0.006690 -0.012212 -0.003677 -0.002367 0.015247 0.000379 -0.023050 -0.012168 -0.002586 -0.027420 -0.024592 -0.026345 -0.017794 0.004438 -0.018960 -0.023756 -0.024513 -0.008514 -0.018544 0.005655 -0.017918 -0.014421 0.040119 0.024237 0.004791 0.024069 -0.000890 0.013066 0.029510 -0.013074 0.011573 0.007058 0.020358 0.020623 -0.022569 0.016365 -0.027804 0.014929 0.011954 0.036268 0.004772 -0.003683 -0.026205 -0.008851 -0.005150 -0.017917 -0.039892 -0.027385 -0.050208 -0.024645 -0.023416 -0.034183 0.017620 -0.005583 0.026526 0.013988 -0.053982 0.042689 -0.010137 0.014961 0.009621 0.001636 0.021516 0.060522 -0.041126 0.033088 0.051550 0.030477 -0.037362 0.003607 0.017596 0.003818 -0.025150 0.011429 0.026123 0.033612 -0.029760 -0.022195 -0.024442 -0.014269 -0.071485 -0.030445 -0.055652 0.036059 0.037714 -0.007024\n0.070000 0.071216 0.074865 0.080943 0.089448 0.100373 0.113709 0.129442 0.147555 0.168022 0.190810 0.215877 0.243167 0.272610 0.304123 0.337600 0.372916 0.409923 0.448443 0.488274 0.529179 0.570888 0.613096 0.655461 0.697600 0.739093 0.779478 0.818256 0.854890 0.888806 0.919401 0.946044 0.968085 0.984861 0.995705 0.999962 0.996991 0.986192 0.967011 0.938964 0.901650 0.854777 0.798173 0.731813 0.655836 0.570562 0.476510 0.374413 0.265227 0.150140 0.030573 0.091828 0.215197 0.337471 0.456415 0.569659 0.674742 0.769165 0.850451 0.916219 0.964257 0.992604 0.999631 0.984129 0.945386 0.883263 0.798259 0.691560 0.565072 0.421432 0.263990 0.096772 0.075603 0.248021 0.415016 0.570933 0.710129 0.827182 0.917130 0.975705 0.999567 0.986525 0.935726 0.847809 0.724997 0.571131 0.391630 0.193367 0.015546 0.226042 0.428472 0.613045 0.770316 0.891696 0.969976 0.999814 0.978161 0.904603 0.781564 0.614375 0.411156 0.182528 0.058863 0.298995 0.523254 0.717337 0.868196 0.964993 0.999957 0.969123 0.872835 0.716000 0.508007 0.262321 0.004268 0.272712 0.523029 0.735790 0.893689 0.983049 0.995128 0.927129 0.782758 0.572271 0.311945 0.022991 0.270067 0.541421 0.766257 0.923099 0.996000 0.976335 0.864004 0.667870 0.405325 0.100975 0.215504 0.512193 0.758121 0.926605 0.998289 0.963596 0.824224 0.593480 0.295309 0.037942 0.368890 0.659240 0.874266 0.987125 0.982435 0.858649 0.628844 0.319689 0.031361 0.380394 0.682491 0.897556 0.995817 0.962239 0.799137 0.526555 0.180179 0.193045 0.541103 0.814159 0.971824 0.989410 0.862148 0.606642 0.259148 0.129203 0.499724 0.794999 0.967898 0.989410 0.853894 0.580811 0.212412 0.192411 0.567321 0.849400 0.989879 0.962935 0.770877 0.444674 0.039455 0.374463 0.723613 0.944528 0.995547 0.865142 0.574968 0.176861 0.255983 0.642240 0.907735 0.999956 0.898895 0.621917 0.221427 0.224562 0.627321 0.905080 0.999871 0.890115 0.596110 0.176938 0.280888 0.680989 0.937476 0.993678 0.835210 0.494237 0.043601 0.418225 0.788502 0.983156 0.956341 0.711821 0.303363 0.176447 0.616823 0.914287 0.997286 0.843965 0.488584 0.014616 0.464377 0.831694 0.996153 0.915190 0.606588 0.145370 0.353805 0.764846 0.982155 0.948220 0.669503 0.216171 0.294922 0.729929 0.973178 0.958272 0.686953 0.230040 0.290378 0.733129 0.976322 0.951311 0.662792 0.188960 0.339008 0.772856 0.988996 0.924152 0.594658 0.093256 0.436343 0.840340 0.999687 0.865692 0.475724 0.056368 0.572869 0.918801 0.988669 0.759313 0.298391 0.254792 0.730908 0.982428 0.929768 0.587251 0.060148 0.486984 0.881381 0.996845 0.794714 0.337661 0.228937 0.722688 0.982915 0.923326 0.561433 0.014313 0.538571 0.914000 0.985959 0.728585 0.226301 0.353125 0.814176 0.999611 0.844658 0.400416 0.182131 0.702878 0.981254 0.919242 0.536639 0.034382 0.594256 0.945583 0.963034 0.638687 0.086375 0.497682 0.904146 0.985903 0.711857 0.179565 0.418761 0.865282 0.995991 0.761470 0.246370 0.360393 0.834527 0.999351 0.792102 0.288649 0.323655 0.815097 0.999980 0.807171 0.308206 0.308493 0.808383 1.000000 0.808735 0.306608 0.314178 0.814364 0.999906 0.797673 0.284955 0.339429 0.831804 0.998831 0.773826 0.244041 0.382541 0.858505 0.994795 0.736242 0.184500 0.441313 0.891369 0.984977 0.683540 0.107116 0.512932 0.926564 0.965991 0.614263 0.013075 0.593911 0.959568 0.934201 0.527226 0.095750 0.679925\n1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 0.682093 0.682093 0.682093 0.682093 0.682093 0.682093 0.682093 0.682093 0.682093 0.682093 0.682093 0.682093 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.673987 0.667925 0.674109 0.679018 0.683805 0.690387 0.699451 0.988007 0.988047 0.987777 0.987446 0.987271 0.987388 0.987796 0.988387 0.989024 0.989606 0.990084 0.990449 0.990719 0.990953 0.992928 0.992906 0.992733 0.992988 0.993648 0.996910 0.997084 0.997113 0.997161 0.997143 0.997159 0.997290 0.997459 0.997617 0.997736 0.997823 0.997961 0.997811 0.997534 0.997155 0.997377 0.997100 0.997168 0.997094 0.995650 0.985679 0.977461 0.971979 0.973590 0.970950 0.967289 0.963586 0.962603 0.958595 0.957556 0.958240 0.959276 0.958487 0.955571 0.953046 0.955060 0.955290 0.954742 0.955560 0.957386 0.957865 0.953958 0.943404 0.943759 0.947447 0.948565 0.948016 0.947072 0.946833 0.946839 0.946642 0.944392 0.937933 0.936069 0.925217 0.929872 0.931906 0.933035 0.933549 0.933267 0.920043 0.909462 0.911203 0.900618 0.879624 0.869792 0.874061 0.852518 0.831101 0.827159 0.827939 0.815774 0.813019 0.817817 0.808959 0.781846 0.763598 0.777791 0.751036 0.755959 0.733688 0.729020 0.722763 0.714658 0.694879 0.675357 0.651439 0.593412 0.571482 0.572234 0.565687 0.523630 0.501503 0.515389 0.491516 0.498500 0.494787 0.442050 0.419904 0.395650 0.338158 0.329762 0.299049 0.318635 0.300324 0.259119 0.266089 0.230615 0.185207 0.163993 0.090987 0.020529 0.031291 0.013716 -0.031539 -0.031937 -0.052874 -0.092756 -0.149181 -0.166068 -0.203322 -0.230767 -0.293809 -0.325584 -0.333478 -0.367480 -0.396886 -0.430482 -0.430670 -0.462315 -0.481984 -0.535120 -0.552208 -0.558435 -0.569160 -0.621746 -0.642798 -0.697528 -0.704693 -0.684360 -0.705436 -0.701783 -0.657638 -0.652712 -0.638780 -0.614260 -0.610277 -0.585313 -0.594874 -0.577200 -0.592912 -0.589065 -0.561189 -0.509947 -0.518737 -0.469955 -0.465643 -0.449568 -0.436099 -0.424037 -0.435284 -0.419462 -0.373963 -0.354579 -0.282045 -0.246174 -0.220531 -0.164446 -0.153000 -0.142575 -0.105870 -0.114617 -0.107866 -0.075475 -0.074960 -0.035086 -0.025446 0.021101 0.009977 0.018832 0.132884 0.090929 0.095279 0.073809 0.054355 -0.042604 -0.053142 -0.055304 -0.080719 -0.071652 -0.077295 -0.033040 -0.022030 -0.060413 -0.093193 -0.112075 -0.018447 -0.020505 0.025279 0.001576 0.013721 0.034944 -0.055036 -0.034656 -0.002992 -0.010370 0.029729 -0.012504 -0.014912 -0.026968 -0.050085 0.001452 -0.031633 -0.082990 -0.100585 -0.134470 -0.162123 -0.177942 -0.151789 -0.149785 -0.164316 -0.186026 -0.197841 -0.182022 -0.194659 -0.204215 -0.226957 -0.202126 -0.210421 -0.224403 -0.211379 -0.200832 -0.147640 -0.121536 -0.110874 -0.065045 -0.050204 -0.026944 -0.022028 -0.048763 -0.062635 -0.033496 -0.059540 -0.110907 -0.146000 -0.159832 -0.131788 -0.103534 -0.117544 -0.084057 -0.156693 -0.198294 -0.187845 -0.085873 -0.085873 -0.085873 -0.085873 -0.085873 -0.085873 -0.085873 -0.085873 -0.085873 -0.085873 -0.065866 -0.065866 -0.065866 -0.065866 -0.065866 -0.065866 -0.065866 -0.065866 -0.065866 -0.065866 -0.091164 -0.091164 -0.091164 -0.091164 -0.091164 -0.091164 -0.091164 -0.091164 -0.091164\n0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.222222 0.222222 0.222222 0.222222 0.222222 0.222222 0.222222 0.222222 0.222222 0.222222 0.222222 0.222222 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.304997 0.304997 0.304997 0.304997 0.304997 0.304997 0.304997 0.304997 0.304997 0.304997 0.304997 0.304997 0.304997 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.328798 0.328798 0.328798 0.328798 0.328798 0.328798 0.328798 0.328798 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.320256 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.304997 0.304997 0.304997 0.304997 0.304997 0.304997 0.304997 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.312348 0.312348 0.312348 0.312348 0.312348 0.312348 0.285714 0.285714 0.285714 0.285714 0.285714 0.285714 0.285714 0.304997 0.304997 0.304997 0.304997 0.304997 0.304997 0.298142 0.298142 0.298142 0.298142 0.298142 0.298142 0.291730 0.291730 0.291730 0.291730 0.291730 0.291730 0.291730 0.291730 0.291730 0.291730 0.291730 0.291730 0.285714 0.285714 0.285714 0.285714 0.285714 0.285714 0.304997 0.304997 0.304997 0.304997 0.304997 0.280056 0.280056 0.280056 0.280056 0.280056 0.280056 0.298142 0.298142 0.298142 0.298142 0.298142 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.285714 0.285714 0.285714 0.285714 0.285714 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.280056 0.280056 0.280056 0.280056 0.280056 0.280056 0.280056 0.280056 0.280056 0.280056 0.274721 0.274721 0.274721 0.274721 0.274721 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.264906 0.264906 0.264906 0.264906 0.264906 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.285714 0.285714 0.285714 0.285714 0.256074 0.256074 0.256074 0.256074 0.256074 0.256074 0.256074 0.256074 0.256074 0.256074 0.251976 0.251976 0.251976 0.251976 0.251976 0.251976 0.251976 0.251976 0.251976 0.251976 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069\n",
    "ctf_analysis_result": {
    "volts": 300000.0,
    "cs": 2.7,
    "apix": 1.0,
    "defocus1": 1.0588083984e-05,
    "defocus2": 9.9566875e-06,
    "angle_astigmatism": -0.7803404086646789,
    "amplitude_contrast": 0.07,
    "extra_phase_shift": 0.0,
    "confidence_30_10": -0.12418697520360525,
    "confidence_5_peak": 0.03076704907898039,
    "overfocus_conf_30_10": -0.17330532796560966,
    "overfocus_conf_5_peak": -0.005424972651162901,
    "resolution_80_percent": 40.71472574015554,
    "resolution_50_percent": 39.178518535174994,
    "confidence": 0.03076704907898039
    },
    "ctf_analysis_images": [
    "/home/pm22p/puneeth/ctf/ouput.mrc-plots.png",
    "/home/pm22p/puneeth/ctf/ouput.mrc-powerspec.jpg",
    "/home/pm22p/puneeth/ctf/ouput.mrc"
    ]
    }
    }




