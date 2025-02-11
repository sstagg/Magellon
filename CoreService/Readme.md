steps to create a virtual environment inside a directory using the command[ReadMe.md](..%2Finfrastructure%2Fdocker%2FReadMe.md) line:

/gpfs/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc
/gpfs/research/stagg/leginondata/23oct13x/rawdata/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc

Open your terminal or command prompt.
    Navigate to the directory where you want to create the virtual environment. You can use the cd command to change directories. For example: cd /path/to/directory
    Once you are in the directory, run the following command to create a new virtual environment:

`python -m venv env`

This will create a new directory called env inside your current directory that contains the virtual environment.
Note: If you have multiple versions of Python installed on your system, you may need to specify the Python version you want to use. For example, to use Python 3.8, you would run: python3.8 -m venv env

Activate the virtual environment by running the following command:

`source env/bin/activate`

This will activate the virtual environment and change your prompt to reflect that you are now working inside it.
Note: If you are using Windows, the activation command is slightly different: env\Scripts\activate
Once you've activated the virtual environment, you can install packages and work on your project without affecting the global Python installation. To exit the virtual environment, simply run the command deactivate.
rm -fr ".git/rebase-merge"
```
# we have used following command to capture requirements:
pip freeze > requirements.txt
# then to install dependencies you need to use:
pip install -r requirements.txt

python.exe -m uvicorn main:app --reload

```

`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Unrestricted
`

https://dassum.medium.com/building-rest-apis-using-fastapi-sqlalchemy-uvicorn-8a163ccf3aa1
ORMs:
https://ponyorm.org/


# Deployment

To deploy a Magellon application to a Debian 11 server, you can follow these general steps:

Install necessary dependencies:

`sudo apt-get update
sudo apt-get install -y python3-pip python3-dev build-essential libffi-dev libssl-dev`

Install uvicorn and gunicorn using pip:

_sudo pip3 install uvicorn gunicorn_

Copy your CoreService files to your Debian 11 server using SCP or any other file transfer method.

Create a virtual environment for your application:

`
python3 -m venv myenv
source myenv/bin/activate
`

Install your application's dependencies inside the virtual environment:

`pip3 install -r requirements.txt`

Test your application locally:

`uvicorn main:app --reload`
`uvicorn main:app --port 8080`

Once your application is running correctly, you can configure a Gunicorn systemd service file. Create a file called /etc/systemd/system/myapp.service with the following content:

```
[Unit]
Description=Gunicorn instance to serve coreservice
After=network.target

[Service]
User=yourusername
Group=www-data
WorkingDirectory=/home/yourusername/myapp
Environment="PATH=/home/yourusername/myenv/bin"
ExecStart=/home/yourusername/myenv/bin/gunicorn --workers 2 --bind unix:/home/yourusername/myapp/myapp.sock main:app

[Install]
WantedBy=multi-user.target
```

Make sure to replace yourusername with your server's username and /home/yourusername/myapp with the path to your application files.

Reload systemd and start the Gunicorn service:

`
sudo systemctl daemon-reload
sudo systemctl start myapp
sudo systemctl enable myapp
`
Test your application by accessing it through a web browser or using curl:

    curl http://localhost/

Congratulations! 


## Dependency Injection
https://python-dependency-injector.ets-labs.org/examples/application-single-container.html
https://python-dependency-injector.ets-labs.org/examples/fastapi.html
https://python-dependency-injector.ets-labs.org/examples/fastapi-sqlalchemy.html
https://kimlehtinen.com/python-flask-dependency-injection/


## Prometus and Grafana
prometheus_client
https://github.com/Kludex/fastapi-prometheus-grafana
https://github.com/Blueswen/fastapi-observability



Components:
https://github.com/Lattice-Automation/seqviz
https://npm.io/package/alignment.js
https://github.com/veg/phylotree.js
https://npm.io/package/igv
https://npm.io/package/pileup
https://www.canvasxpress.org
https://npm.io/package/lexicon-mono-seq

https://npm.io/package/vue-svg-msa

https://npm.io/package/ntseq
https://npm.io/package/static-interval-tree
https://npm.io/package/dna
https://npm.io/package/bionode-seq
https://www.bionode.io/


ssh -N -L 3310:kriosdb.rcc.fsu.edu:3306 bk2n@hpc-login.rcc.fsu.edu
hpc-login.rcc.fsu.edu
maia.cryoem.fsu.edu
sshfs bk22n@hpc-login.rcc.fsu.edu:/gpfs /rcc_gpfs


```WITH RECURSIVE image_hierarchy AS (
-- Anchor member: get the initial level (level 0)
SELECT oid, name, parent_id, 0 AS level
FROM image
WHERE parent_id IS NULL

    UNION ALL
    
    -- Recursive member: traverse the hierarchy based on the specified level number
    SELECT c.oid, c.name, c.parent_id, h.level + 1
    FROM image AS c
    JOIN image_hierarchy AS h ON c.parent_id = h.oid
    WHERE h.level < :level_number -- Specify the desired level number
)
SELECT parent.oid AS parent_oid, parent.name AS parent_name, COUNT(child.oid) AS num_images
FROM image_hierarchy AS child
JOIN image_hierarchy AS parent ON child.parent_id = parent.oid
WHERE child.level = :level_number - 1 -- Specify the level of the children (one level below the parent)
GROUP BY parent.oid, parent.name
HAVING COUNT(child.oid) >= :num_images -- Specify the minimum number of images
ORDER BY parent.oid;```



WITH RECURSIVE cte AS (
    -- Anchor query: Set level 0 for root images
    SELECT oid, parent_id, 0 AS level
    FROM image
    WHERE parent_id IS NULL
    UNION ALL
    -- Recursive query: Update level for child images
    SELECT i.oid, i.parent_id, cte.level + 1
    FROM image AS i
    JOIN cte ON i.parent_id = cte.oid
)
UPDATE image AS t
JOIN cte ON t.oid = cte.oid
SET t.level = cte.level;



./MotionCor3 -InMrc 23oct13a_a_00038gr_00001sq_v02_00005hl_00002ex.tif -OutMrc outImg.mrc -kV 300 -Cs 2.7 -PixSize 0.93 FmDose 0.6 -Gain ./K3-20310049.mrc

```

1.Create MagellonSDK
2.Pass Environment Variables
3.Service Discovery
4.


## Installation 1
pip freeze > requirements.txt
pip download -r requirements.txt --no-binary :all:
pip install --no-index --find-links=/path/to/local/directory -r requirements.txt

## Installation 2
pip download -r requirements.txt -d /path/to/wheelhouse
pip install --no-index --find-links=/path/to/wheelhouse -r requirements.txt

pip download --only-binary=:all: --platform manylinux1_x86_64,win_amd64,macosx_10_15_x86_64 -r requirements.txt -d /path/to/wheelhouse

    --only-binary=:all:: Instructs pip to consider all platforms when looking for pre-built binary distributions (wheels).
    --platform manylinux1_x86_64,win_amd64,macosx_10_15_x86_64: Specifies the platforms for which to download wheels. In this example, it includes Linux (manylinux1_x86_64), Windows (win_amd64), and macOS (macosx_10_15_x86_64). You can customize the platform list based on your requirements.



{
    "session_name": "24dec03a",
    "magellon_project_name": "Leginon",
    "magellon_session_name": "24dec03a",
    "camera_directory": "/gpfs",
    "copy_images": false,
    "retries": 0,
    "leginon_mysql_user": "usr_object",
    "leginon_mysql_pass": "ThPHMn3m39Ds",
    "leginon_mysql_host": "localhost",
    "leginon_mysql_port": 3310,
    "leginon_mysql_db": "dbemdata",
    "replace_type": "standard",
    "replace_pattern": "/gpfs",
    "replace_with": "Y:\\"
}


example motioncor task in motioncor_tasks_queue
{"id":"673f9660-7cd4-4c0a-9f1f-8669a7d77aa4","sesson_id":null,"sesson_name":"24dec03a","worker_instance_id":"8c6c7cd7-39b6-4091-83b4-421054e0787a","data":{"image_id":"79087b7e-0cfd-4e1d-95ad-a39bee7d8b8d","image_name":"Image1","image_path":"/gpfs/frames/20241203_54458_integrated_movie.mrc.tif","InMrc":null,"InTiff":null,"InEer":null,"inputFile":"/gpfs/frames/20241203_54458_integrated_movie.mrc.tif","OutMrc":"output.files.mrc","outputFile":"output.mrc","Gain":"/gpfs/20241202_53597_gain_multi_ref.tif","Dark":null,"DefectFile":null,"DefectMap":null,"PatchesX":5,"PatchesY":5,"Iter":5,"Tol":0.5,"Bft":100,"LogDir":".","Gpu":"0","FtBin":2.0,"FmDose":0.75,"PixSize":0.705,"kV":300,"Cs":0,"AmpCont":0.07,"ExtPhase":0.0,"SumRangeMinDose":0,"SumRangeMaxDose":0,"Group":3,"RotGain":0,"FlipGain":0,"InvGain":null},"status":{"code":0,"name":"pending","description":"Task is pending"},"type":{"code":5,"name":"MotionCor","description":"Motion correction for electron microscopy"},"created_date":"2025-02-04T14:54:12.073375","start_on":null,"end_on":null,"result":null,"job_id":"a9c2ea71-725c-49e8-b6c9-2d5552882a15"}

task result in its output: motioncor_out_tasks_queue , simple now but can contain files and metadata parts
{"worker_instance_id":"e82a1547-c977-4dbb-af4c-c2c7d6c6e545","job_id":"fc4a7b5d-3019-4c27-8973-868e4e31243f","task_id":"dd76a7d5-0474-450e-9f24-611be6a2a404","image_id":"ffc7eaa9-5596-4f88-a379-2133653bbd86","image_path":"/gpfs/frames/20241203_54449_integrated_movie.mrc.tif","session_id":null,"session_name":"24dec03a","code":200,"message":"Motioncor executed successfully","description":"Output for Motioncor for an input file","status":{"code":0,"name":"pending","description":"Task is pending"},"type":{"code":5,"name":"MotionCor","description":"Motion correction for electron microscopy"},"created_date":"2025-02-04T19:46:41.004505","started_on":null,"ended_on":"2025-02-04T19:46:41.004509","meta_data":[],"output_files":[{"name":"patchFrameAlignment","path":"/jobs/ffc7eaa9-5596-4f88-a379-2133653bbd86/20241203_54449_integrated_movie-Patch-Frame.log","required":true},{"name":"patchFullAlignment","path":"/jobs/ffc7eaa9-5596-4f88-a379-2133653bbd86/20241203_54449_integrated_movie-Patch-Full.log","required":true},{"name":"patchAlignment","path":"/jobs/ffc7eaa9-5596-4f88-a379-2133653bbd86/20241203_54449_integrated_movie-Patch-Patch.log","required":true},{"name":"outputDWMrc","path":"/jobs/ffc7eaa9-5596-4f88-a379-2133653bbd86/output_DW.mrc","required":true}]}


ctf_out_tasks_queue
{"worker_instance_id":"f8304441-a755-4a8c-8ea0-3814ce1743c7","job_id":"7fa4f982-1993-454e-9f54-43f2ecacb01c","task_id":"547317de-62af-416e-8a92-174bc6522f96","image_id":"11bf14b8-cf4c-4be7-896a-30c64aca02ca","image_path":"/gpfs/24dec03a/rawdata\\24dec03a_00034gr_00003sq_v01_00002hl_00002ex.mrc","session_id":null,"session_name":"24dec03a","code":200,"message":"CTF executed successfully","description":"Output for CTF estimation and evaluation for an input file","status":{"code":0,"name":"pending","description":"Task is pending"},"type":{"code":2,"name":"CTF","description":"Contrast Transfer Function"},"created_date":"2025-02-04T19:51:37.040081","started_on":null,"ended_on":"2025-02-04T19:51:37.040084","output_data":{"output_txt":"# Output from CTFFind version 4.1.14, run on 2025-02-04 19:51:33\n# Input file: /gpfs/24dec03a/rawdata/24dec03a_00034gr_00003sq_v01_00002hl_00002ex.mrc ; Number of micrographs: 1\n# Pixel size: 0.395 Angstroms ; acceleration voltage: 300.0 keV ; spherical aberration: 2.70 mm ; amplitude contrast: 0.07\n# Box size: 512 pixels ; min. res.: 30.0 Angstroms ; max. res.: 5.0 Angstroms ; min. def.: 5000.0 um; max. def. 50000.0 um\n# Columns: #1 - micrograph number; #2 - defocus 1 [Angstroms]; #3 - defocus 2; #4 - azimuth of astigmatism; #5 - additional phase shift [radians]; #6 - cross correlation; #7 - spacing (in Angstroms) up to which CTF rings were fit successfully\n1.000000 5881.591797 5851.229004 -21.575969 0.000000 0.242603 4.598205\n","output_avrot":"# Output from CTFFind version 4.1.14, run on 2025-02-04 19:51:33\n# Input file: /gpfs/24dec03a/rawdata/24dec03a_00034gr_00003sq_v01_00002hl_00002ex.mrc ; Number of micrographs: 1\n# Pixel size: 0.395 Angstroms ; acceleration voltage: 300.0 keV ; spherical aberration: 2.70 mm ; amplitude contrast: 0.07\n# Box size: 512 pixels ; min. res.: 30.0 Angstroms ; max. res.: 5.0 Angstroms ; min. def.: 5000.0 um; max. def. 50000.0 um; num. frames averaged: 1\n# 6 lines per micrograph: #1 - spatial frequency (1/Angstroms); #2 - 1D rotational average of spectrum (assuming no astigmatism); #3 - 1D rotational average of spectrum; #4 - CTF fit; #5 - cross-correlation between spectrum and CTF fit; #6 - 2sigma of expected cross correlation of noise\n0.000000 0.001394 0.002788 0.004182 0.005576 0.006970 0.008364 0.009759 0.011153 0.012547 0.013941 0.015335 0.016729 0.018123 0.019517 0.020911 0.022305 0.023699 0.025093 0.026487 0.027882 0.029276 0.030670 0.032064 0.033458 0.034852 0.036246 0.037640 0.039034 0.040428 0.041822 0.043216 0.044610 0.046005 0.047399 0.048793 0.050187 0.051581 0.052975 0.054369 0.055763 0.057157 0.058551 0.059945 0.061339 0.062734 0.064128 0.065522 0.066916 0.068310 0.069704 0.071098 0.072492 0.073886 0.075280 0.076674 0.078068 0.079462 0.080857 0.082251 0.083645 0.085039 0.086433 0.087827 0.089221 0.090615 0.092009 0.093403 0.094797 0.096191 0.097585 0.098980 0.100374 0.101768 0.103162 0.104556 0.105950 0.107344 0.108738 0.110132 0.111526 0.112920 0.114314 0.115708 0.117103 0.118497 0.119891 0.121285 0.122679 0.124073 0.125467 0.126861 0.128255 0.129649 0.131043 0.132437 0.133831 0.135226 0.136620 0.138014 0.139408 0.140802 0.142196 0.143590 0.144984 0.146378 0.147772 0.149166 0.150560 0.151954 0.153349 0.154743 0.156137 0.157531 0.158925 0.160319 0.161713 0.163107 0.164501 0.165895 0.167289 0.168683 0.170078 0.171472 0.172866 0.174260 0.175654 0.177048 0.178442 0.179836 0.181230 0.182624 0.184018 0.185412 0.186806 0.188201 0.189595 0.190989 0.192383 0.193777 0.195171 0.196565 0.197959 0.199353 0.200747 0.202141 0.203535 0.204929 0.206324 0.207718 0.209112 0.210506 0.211900 0.213294 0.214688 0.216082 0.217476 0.218870 0.220264 0.221658 0.223052 0.224447 0.225841 0.227235 0.228629 0.230023 0.231417 0.232811 0.234205 0.235599 0.236993 0.238387 0.239781 0.241175 0.242570 0.243964 0.245358 0.246752 0.248146 0.249540 0.250934 0.252328 0.253722 0.255116 0.256510 0.257904 0.259298 0.260693 0.262087 0.263481 0.264875 0.266269 0.267663 0.269057 0.270451 0.271845 0.273239 0.274633 0.276027 0.277422 0.278816 0.280210 0.281604 0.282998 0.284392 0.285786 0.287180 0.288574 0.289968 0.291362 0.292756 0.294150 0.295545 0.296939 0.298333 0.299727 0.301121 0.302515 0.303909 0.305303 0.306697 0.308091 0.309485 0.310879 0.312273 0.313668 0.315062 0.316456 0.317850 0.319244 0.320638 0.322032 0.323426 0.324820 0.326214 0.327608 0.329002 0.330396 0.331791 0.333185 0.334579 0.335973 0.337367 0.338761 0.340155 0.341549 0.342943 0.344337 0.345731 0.347125 0.348519 0.349914 0.351308 0.352702 0.354096 0.355490 0.356884 0.358278 0.359672 0.361066 0.362460 0.363854 0.365248 0.366642 0.368037 0.369431 0.370825 0.372219 0.373613 0.375007 0.376401 0.377795 0.379189 0.380583 0.381977 0.383371 0.384766 0.386160 0.387554 0.388948 0.390342 0.391736 0.393130 0.394524 0.395918 0.397312 0.398706 0.400100 0.401494 0.402889 0.404283 0.405677 0.407071 0.408465 0.409859 0.411253 0.412647 0.414041 0.415435 0.416829 0.418223 0.419617 0.421012 0.422406 0.423800 0.425194 0.426588 0.427982 0.429376 0.430770 0.432164 0.433558 0.434952 0.436346 0.437740 0.439135 0.440529 0.441923 0.443317 0.444711 0.446105 0.447499 0.448893 0.450287 0.451681 0.453075 0.454469 0.455863 0.457258 0.458652 0.460046 0.461440 0.462834 0.464228 0.465622 0.467016 0.468410 0.469804 0.471198 0.472592 0.473987 0.475381 0.476775 0.478169 0.479563 0.480957 0.482351 0.483745 0.485139 0.486533 0.487927 0.489321 0.490715 0.492110 0.493504 0.494898 0.496292 0.497686 0.499080 0.500474 0.501868 0.503262 0.504656\n      -0.05677       -0.05271       -0.04932       -0.04811       -0.04759       -0.04715       -0.04699       -0.04680       -0.04667       -0.04659       -0.04649       -0.04646       -0.04638       -0.04634       -0.04631       -0.04627       -0.04625       -0.04621       -0.04620       -0.04617       -0.04616       -0.04614       -0.04612       -0.03656       -0.00577       -1.67275       -3.10685       -2.95812       -2.28349       -0.93336        0.59879        1.25483        1.97315        2.11568        2.64832        2.63068        1.37344        0.49755       -0.53319       -0.76961       -1.18313       -0.93948       -0.44727       -0.00409        0.30918        0.47258        0.39440        0.13935       -0.41213       -0.40046       -0.39456       -0.21907       -0.29158       -0.13095       -0.24306       -0.21167       -0.12857       -0.20649       -0.33979       -0.34845       -0.54983       -0.47777       -0.75671       -0.67412       -0.64487       -0.68048       -0.71385       -0.72189       -0.67992       -0.62426       -0.54396       -0.46041       -0.29695       -0.13949       -0.09146        0.02851        0.14020        0.26540        0.29619        0.27803        0.39325        0.48957        0.37821        0.40679        0.37580        0.24782        0.22990        0.22937        0.06241       -0.02268       -0.17821       -0.23304       -0.34765       -0.45568       -0.48073       -0.55085       -0.48311       -0.53084       -0.38800       -0.15465       -0.10959       -0.04034        0.17609        0.32897        0.35699        0.37885        0.41838        0.45927        0.39246        0.29571        0.20223        0.10653       -0.01611       -0.23278       -0.34759       -0.42600       -0.45329       -0.48439       -0.35035       -0.24976       -0.17077       -0.02408        0.13391        0.27226        0.21808        0.30344        0.26601        0.25300        0.15304        0.12869       -0.01592       -0.07246       -0.16185       -0.30103       -0.32053       -0.28607       -0.21521       -0.23282       -0.13832       -0.00777        0.09227        0.18374        0.14556        0.20129        0.15012        0.03664       -0.02435       -0.11289       -0.17294       -0.19760       -0.26867       -0.19678       -0.17598       -0.06360        0.01363        0.01519        0.10488        0.17057        0.19844        0.12509        0.06024       -0.02631       -0.05562       -0.11922       -0.18171       -0.18211       -0.15455       -0.08642       -0.02526        0.08129        0.05840        0.05334        0.09245        0.04508       -0.08507       -0.13960       -0.10777       -0.16797       -0.14322       -0.07661       -0.08029       -0.09550        0.02463        0.07771        0.05576        0.04440        0.01613       -0.03316       -0.02472       -0.15102       -0.10643       -0.12139       -0.04276       -0.00201       -0.02282        0.01540        0.02071        0.02152        0.02699       -0.05998       -0.15931       -0.10524       -0.10848       -0.06718       -0.05563        0.02688        0.02472        0.07761        0.02001       -0.03178       -0.04105       -0.05236       -0.09044       -0.08310       -0.07216       -0.01052        0.00167        0.01168        0.03204       -0.02267       -0.03054       -0.03343       -0.11949       -0.13044       -0.05672       -0.05041       -0.03936       -0.02987        0.00158       -0.00356       -0.04170       -0.05106       -0.06444       -0.12925       -0.07783       -0.06356       -0.03541        0.00939        0.02685        0.01398       -0.03763       -0.13582       -0.08690       -0.05843        0.00126        0.00847       -0.01677       -0.00497       -0.00893       -0.03596       -0.09884       -0.06480       -0.05670       -0.03610       -0.00874       -0.03234        0.00177       -0.03360       -0.03970       -0.06989       -0.07131       -0.09723       -0.07953       -0.01342       -0.05618       -0.01936       -0.00494       -0.04417       -0.10729       -0.06184       -0.07840       -0.03275       -0.02640        0.00967       -0.01783       -0.05679       -0.08383       -0.06743       -0.01001        0.01029       -0.03503       -0.06790       -0.02748       -0.15860       -0.10762       -0.06281       -0.03477       -0.02216       -0.03135        0.04486       -0.03378       -0.02690       -0.08925       -0.10151       -0.13472        0.03529        0.01405        0.06612       -0.03913       -0.02234       -0.03856       -0.05364        0.01985        0.00072       -0.02990        0.00011       -0.11598       -0.11565       -0.04217       -0.02007       -0.01647       -0.01051       -0.02002        0.01422       -0.11737       -0.14381       -0.19751       -0.05370        0.02603       -0.01680       -0.01051       -0.09965       -0.09629       -0.12427       -0.04175        0.01587       -0.14402       -0.10852        0.03663        0.08018       -0.00486       -0.15503       -0.09860        0.04309        0.05730       -0.10478       -0.10992       -0.01281       -0.08507       -0.27074       -0.12106       -0.04307       -0.00439       -0.16915       -0.06105        0.00384       -0.06781       -0.08922       -0.21952       -0.22974       -0.01114       -0.23633       -0.11578        0.06439        0.08912        0.46936        0.82548        0.77174        0.77758        0.64447        0.09297        0.91281        1.72205\n0.809206 0.814576 0.811592 0.808611 0.805633 0.802659 0.799689 0.796722 0.793758 0.790798 0.787755 0.784650 0.781533 0.778406 0.775238 0.772027 0.768801 0.765554 0.762282 0.758994 0.755686 0.752360 0.731961 0.691564 0.277851 -0.732342 -1.402972 -1.686173 -1.125076 -0.174939 0.944400 1.835288 2.431457 2.734649 2.983794 3.043416 2.162936 1.257313 0.498534 -0.018380 -0.247962 -0.159624 0.255795 0.659845 0.944806 1.089778 1.077928 0.827354 0.435735 0.317832 0.336852 0.454148 0.421899 0.544737 0.484661 0.447509 0.527912 0.499109 0.359530 0.372076 0.176195 0.172496 -0.004794 -0.015211 0.042236 0.023948 -0.014175 -0.047002 -0.003532 0.025044 0.123696 0.139809 0.317654 0.424995 0.476129 0.609562 0.678731 0.810390 0.824382 0.796565 0.923185 0.969613 0.933186 0.916880 0.908283 0.803695 0.722308 0.797460 0.629301 0.510118 0.383298 0.324843 0.252943 0.096176 0.153950 0.052244 0.053590 0.015238 0.053124 0.355181 0.359733 0.374295 0.582010 0.724462 0.778381 0.786583 0.813889 0.915517 0.843462 0.732615 0.656079 0.612754 0.493555 0.289160 0.091445 0.041376 0.006643 -0.053873 0.086122 0.140437 0.225726 0.305552 0.454828 0.629041 0.558135 0.619278 0.623397 0.564297 0.481034 0.503085 0.377331 0.259151 0.241100 0.109540 0.008016 0.013820 0.130085 0.112418 0.083390 0.239158 0.261943 0.470722 0.439866 0.386082 0.469216 0.291090 0.207751 0.108579 0.086974 0.110939 -0.013733 0.055364 0.012947 0.146091 0.250000 0.200816 0.299111 0.242596 0.443287 0.375922 0.169884 0.154615 0.049285 0.073656 -0.033782 -0.030708 -0.041977 0.010982 0.041397 0.145882 0.242594 0.162489 0.164319 0.243970 0.002507 -0.055774 -0.045770 -0.007910 -0.074837 -0.061321 -0.005678 -0.076850 -0.036000 0.123421 0.095159 0.058800 0.074088 -0.027433 0.031880 -0.023736 -0.116871 -0.102900 -0.077580 0.053040 -0.042878 0.021093 -0.015901 0.006155 0.041890 -0.043085 -0.136374 -0.130236 -0.108228 -0.081921 -0.028259 0.007825 0.075343 -0.014399 0.041452 -0.020569 -0.070874 -0.105722 -0.069030 -0.071726 -0.070168 -0.013897 0.012025 0.029485 0.020022 0.012350 -0.018159 0.024983 0.005884 -0.203633 -0.150302 0.004243 0.015675 -0.002810 0.030546 0.077432 0.022761 -0.053117 -0.027492 0.006119 -0.116153 0.043660 -0.066670 0.034736 0.069138 0.022732 -0.002694 -0.042603 -0.066141 -0.008327 -0.015182 0.095442 0.018892 0.030039 0.051037 0.046851 -0.063908 -0.142357 -0.063503 -0.019545 -0.002061 0.014587 0.002603 0.076018 -0.064355 -0.000696 -0.087084 -0.045924 -0.081428 -0.118781 0.066872 -0.082135 -0.021875 0.046423 -0.125403 -0.047233 -0.042145 -0.043516 -0.059638 0.022641 0.100748 -0.063466 -0.001003 0.035750 -0.041523 0.032593 -0.084655 0.031992 -0.034332 -0.008641 -0.201970 0.004167 -0.040716 -0.006008 -0.024878 -0.018960 0.036635 0.105122 -0.057899 -0.130436 -0.063353 0.045405 -0.038903 0.037819 0.028300 0.046543 0.085044 0.065561 -0.050075 0.126011 0.067704 0.094457 0.155039 -0.055617 -0.050465 0.090961 0.048539 -0.006414 0.112649 0.057489 0.067465 -0.027849 -0.085486 -0.083634 -0.033804 0.146487 0.283366 -0.088636 0.138790 0.055823 0.011605 0.077817 0.059320 -0.028029 -0.083893 0.150159 0.184673 0.010602 0.005439 -0.192232 0.020050 -0.091824 0.019123 -0.356437 -0.048211 -0.327992 -0.292756 -0.152813 -0.314993 -0.094455 -0.317450 -0.256063 -0.198340 -0.192243 -0.397178 -0.362267 0.007269 -0.117896 -0.214881 -0.079003 0.422220 -0.003169 0.561499 0.535879 0.109329 0.995729 -0.151939 0.504603 0.785947\n0.070000 0.070703 0.072812 0.076327 0.081246 0.087567 0.095288 0.104405 0.114913 0.126805 0.140075 0.154711 0.170700 0.188028 0.206674 0.226617 0.247827 0.270274 0.293918 0.318716 0.344616 0.371561 0.399483 0.428307 0.457948 0.488313 0.519294 0.550777 0.582632 0.614720 0.646888 0.678969 0.710786 0.742146 0.772845 0.802666 0.831378 0.858739 0.884497 0.908389 0.930143 0.949481 0.966117 0.979764 0.990133 0.996937 0.999893 0.998727 0.993173 0.982985 0.967933 0.947812 0.922443 0.891684 0.855426 0.813606 0.766206 0.713262 0.654865 0.591168 0.522389 0.448813 0.370798 0.288773 0.203245 0.114794 0.024073 0.068189 0.161198 0.254092 0.345951 0.435806 0.522646 0.605428 0.683092 0.754572 0.818814 0.874792 0.921528 0.958103 0.983689 0.997557 0.999104 0.987871 0.963561 0.926057 0.875437 0.811987 0.736215 0.648853 0.550862 0.443434 0.327983 0.206135 0.079712 0.049291 0.178731 0.306350 0.429815 0.546759 0.654829 0.751734 0.835300 0.903526 0.954634 0.987129 0.999845 0.991992 0.963202 0.913556 0.843614 0.754427 0.647543 0.524990 0.389260 0.243269 0.090300 0.066051 0.221968 0.373490 0.516629 0.647462 0.762251 0.857561 0.930371 0.978182 0.999118 0.992014 0.956484 0.892971 0.802776 0.688057 0.551801 0.397766 0.230400 0.054724 0.123813 0.299483 0.466480 0.619096 0.751943 0.860137 0.939509 0.986771 0.999686 0.977183 0.919452 0.827983 0.705568 0.556243 0.385185 0.198550 0.003272 0.193182 0.383097 0.558813 0.713036 0.839159 0.931568 0.985906 0.999317 0.970609 0.900377 0.791034 0.646765 0.473412 0.278253 0.069727 0.142921 0.350028 0.541973 0.709614 0.844751 0.940542 0.991886 0.995717 0.951226 0.859969 0.725856 0.555031 0.355627 0.137399 0.088729 0.311198 0.518400 0.699298 0.844034 0.944481 0.994737 0.991510 0.934364 0.825824 0.671315 0.478926 0.259028 0.023740 0.213721 0.439782 0.641283 0.806270 0.924719 0.989186 0.995306 0.942134 0.832276 0.671820 0.470035 0.238877 0.007694 0.254540 0.486274 0.688219 0.847363 0.953221 0.998563 0.979948 0.898028 0.757583 0.567298 0.339257 0.088209 0.169360 0.416305 0.635969 0.813317 0.935993 0.995220 0.986459 0.909806 0.770064 0.576490 0.342220 0.083404 0.181880 0.434883 0.657524 0.833687 0.950414 0.998904 0.975206 0.880583 0.721505 0.509234 0.259073 0.010712 0.280220 0.529380 0.739434 0.894411 0.982325 0.996166 0.934487 0.801587 0.607247 0.366055 0.096330 0.181256 0.445254 0.675095 0.852715 0.964001 0.999931 0.957350 0.839280 0.654731 0.418061 0.147868 0.134451 0.406381 0.646118 0.834281 0.955547 0.999898 0.963483 0.848983 0.665444 0.427580 0.154624 0.131224 0.406606 0.648895 0.838099 0.958503 1.000000 0.958969 0.838608 0.648705 0.404864 0.127228 0.161172 0.436324 0.675264 0.857970 0.969073 0.999162 0.945594 0.812744 0.611652 0.359128 0.076335 0.212970 0.484442 0.715209 0.885789 0.981764 0.994992 0.924317 0.775665 0.561558 0.300046 0.013210 0.274748 0.539510 0.758731 0.913925 0.992011 0.986432 0.897706 0.733358 0.507284 0.238566 0.050136 0.334524 0.590708 0.797207 0.936757 0.997750 0.975193 0.871103 0.694316 0.459708 0.186940 0.101205 0.380737 0.628478 0.823966 0.951142 0.999673 0.965755 0.852396 0.669134 0.431204 0.158241 0.127373 0.402301 0.644230 0.833637 0.955388 0.999889 0.963849 0.850470 0.669139 0.434621 0.165828 0.115750 0.387751 0.628744 0.819898 0.946457 0.998831 0.973314 0.872284 0.703952\n1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 1.000000 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.334830 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.305096 0.304492 0.297020 0.286677 0.282252 0.291011 0.307652 0.324488 0.340218 0.349725 0.358778 0.368377 0.382036 0.400155 0.402201 0.407041 0.927117 0.946370 0.960146 0.961521 0.962758 0.962460 0.962106 0.962133 0.964670 0.968389 0.969103 0.970774 0.972674 0.972277 0.978151 0.984290 0.984303 0.984343 0.984699 0.980579 0.979675 0.964558 0.964441 0.959210 0.958889 0.965572 0.965295 0.959368 0.957708 0.956251 0.954571 0.954288 0.954518 0.955715 0.956928 0.957409 0.954591 0.951203 0.947241 0.937390 0.935641 0.934166 0.935371 0.926443 0.924293 0.924403 0.923293 0.920374 0.919881 0.920151 0.920500 0.896877 0.873827 0.829585 0.806100 0.775386 0.766451 0.771478 0.777523 0.780076 0.774058 0.761818 0.754028 0.738825 0.735043 0.694071 0.634882 0.594888 0.579418 0.556128 0.548704 0.540307 0.545748 0.537961 0.484937 0.461677 0.458094 0.464191 0.450469 0.455047 0.432647 0.380409 0.379613 0.376068 0.343460 0.342279 0.287836 0.260783 0.232648 0.206069 0.178525 0.122383 0.068756 0.036305 0.022565 0.028648 0.010942 -0.014330 -0.055687 -0.115472 -0.111443 -0.106151 -0.115460 -0.134218 -0.175320 -0.206952 -0.185428 -0.180788 -0.148058 -0.133082 -0.152222 -0.209166 -0.275007 -0.334508 -0.344536 -0.334145 -0.342034 -0.323724 -0.334385 -0.315084 -0.297350 -0.272058 -0.234901 -0.218182 -0.188087 -0.178143 -0.195567 -0.191608 -0.225180 -0.267537 -0.253281 -0.247937 -0.226965 -0.230143 -0.227955 -0.195954 -0.194937 -0.181140 -0.178140 -0.160853 -0.152778 -0.139163 -0.158759 -0.154875 -0.155788 -0.173711 -0.180189 -0.169036 -0.138910 -0.104103 -0.110087 -0.118354 -0.138751 -0.144372 -0.142054 -0.097540 -0.097531 -0.105810 -0.125358 -0.081415 -0.083913 -0.107394 -0.135735 -0.174281 -0.167253 -0.124369 -0.098188 -0.052970 -0.037507 -0.026955 -0.028206 -0.013872 -0.050942 -0.052941 -0.089360 -0.096378 -0.113210 -0.118477 -0.135884 -0.144282 -0.178137 -0.164243 -0.178739 -0.186234 -0.180919 -0.215629 -0.238582 -0.237085 -0.259367 -0.258479 -0.253837 -0.248431 -0.247766 -0.229459 -0.267375 -0.228567 -0.237720 -0.231292 -0.223866 -0.247300 -0.239584 -0.211684 -0.210165 -0.187427 -0.187777 -0.197689 -0.212993 -0.223407 -0.212138 -0.239401 -0.171439 -0.163746 -0.194325 -0.200685 -0.183792 -0.182768 -0.188436 -0.199699 -0.175148 -0.146152 -0.171777 -0.157667 -0.180098 -0.162844 -0.161882 -0.153786 -0.144605 -0.200078 -0.196378 -0.197170 -0.174753 -0.175286 -0.184340 -0.207435 -0.191584 -0.178271 -0.205290 -0.192277 -0.200127 -0.163519 -0.169146 -0.133428 -0.156001 -0.151593 -0.144581 -0.152631 -0.152631 -0.152631 -0.152631 -0.152631 -0.152631 -0.152631 -0.152631 -0.152631 -0.152631 -0.152631 -0.146910 -0.146910 -0.146910 -0.146910 -0.146910 -0.146910 -0.146910 -0.146910 -0.146910 -0.146910 -0.146910 -0.155859 -0.155859 -0.155859 -0.155859 -0.155859 -0.155859 -0.155859 -0.155859 -0.155859 -0.155859 -0.155859 -0.155859 -0.155859 -0.155859\n0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.195180 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.214423 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.274721 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.269680 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.264906 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.248069 0.251976 0.251976 0.251976 0.251976 0.251976 0.251976 0.251976 0.251976 0.251976 0.251976 0.251976 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.260378 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.244339 0.240772 0.240772 0.240772 0.240772 0.240772 0.240772 0.240772 0.240772 0.240772 0.240772 0.240772 0.234082 0.234082 0.234082 0.234082 0.234082 0.234082 0.234082 0.234082 0.234082 0.234082 0.234082 0.230940 0.230940 0.230940 0.230940 0.230940 0.230940 0.230940 0.230940 0.230940 0.230940 0.230940 0.227921 0.227921 0.227921 0.227921 0.227921 0.227921 0.227921 0.227921 0.227921 0.227921 0.227921 0.225018 0.225018 0.225018 0.225018 0.225018 0.225018 0.225018 0.225018 0.225018 0.225018 0.225018 0.225018 0.225018 0.225018\n"},"meta_data":[{"key":"volts","value":"300000.0","is_persistent":null,"image_id":null},{"key":"cs","value":"2.7","is_persistent":null,"image_id":null},{"key":"apix","value":"0.395","is_persistent":null,"image_id":null},{"key":"defocus1","value":"5.881591797e-07","is_persistent":null,"image_id":null},{"key":"defocus2","value":"5.851229004000001e-07","is_persistent":null,"image_id":null},{"key":"angle_astigmatism","value":"-0.37657169835822846","is_persistent":null,"image_id":null},{"key":"amplitude_contrast","value":"0.07","is_persistent":null,"image_id":null},{"key":"extra_phase_shift","value":"0.0","is_persistent":null,"image_id":null},{"key":"confidence_30_10","value":"0.9914564792463073","is_persistent":null,"image_id":null},{"key":"confidence_5_peak","value":"0.8911648557665833","is_persistent":null,"image_id":null},{"key":"overfocus_conf_30_10","value":"0.9830384722784993","is_persistent":null,"image_id":null},{"key":"overfocus_conf_5_peak","value":"0.8051660511265406","is_persistent":null,"image_id":null},{"key":"resolution_80_percent","value":"5.1548762489544195","is_persistent":null,"image_id":null},{"key":"resolution_50_percent","value":"4.6338915180883","is_persistent":null,"image_id":null},{"key":"confidence","value":"0.9914564792463073","is_persistent":null,"image_id":null}],"output_files":[{"name":"ctfevalplots","path":"/jobs/547317de-62af-416e-8a92-174bc6522f96/24dec03a_00034gr_00003sq_v01_00002hl_00002ex_ctf_output.mrc-plots.png","required":true},{"name":"ctfevalpowerspec","path":"/jobs/547317de-62af-416e-8a92-174bc6522f96/24dec03a_00034gr_00003sq_v01_00002hl_00002ex_ctf_output.mrc-powerspec.jpg","required":true},{"name":"ctfestimationOutputFile","path":"/jobs/547317de-62af-416e-8a92-174bc6522f96/24dec03a_00034gr_00003sq_v01_00002hl_00002ex_ctf_output.mrc","required":true},{"name":"ctfestimationOutputTextFile","path":"/jobs/547317de-62af-416e-8a92-174bc6522f96/24dec03a_00034gr_00003sq_v01_00002hl_00002ex_ctf_output.txt","required":true},{"name":"ctfestimationOutputAvrotFile","path":"/jobs/547317de-62af-416e-8a92-174bc6522f96/24dec03a_00034gr_00003sq_v01_00002hl_00002ex_ctf_output_avrot.txt","required":true}]}

