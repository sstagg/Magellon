

suppose: 
needs to access : /rcc_gpfs/research/secm4/leginondata/24jun28a/rawdata/24jun28a_Valle001-01_00003gr.mrc
can only access /gpfs which mounted to /rcc_gpfs then docker image should access:
/gpfs/research/secm4/leginondata/24jun28a/rawdata/24jun28a_Valle001-01_00003gr.mrc
in file path /rcc_gpfs/ have to be replaced with /gpfs/

sshfs -o reconnect,ServerAliveInterval=15,ServerAliveCountMax=3 bk22n@hpc-login.rcc.fsu.edu:/gpfs /rcc_gpfs
docker build -t magellon_ctf_plugin .

sudo docker run \
-v /rcc_gpfs/research:/gpfs \
-v /magellon/jobs:/outputs \
-e APP_ENV=production \
-p 8181:80 \
--name magellon_ctf_plugin_container \
magellon_ctf_plugin_image

sudo docker run \
-v C:\temp\magellon:/gpfs \
-v C:\temp\magellon\jobs:/outputs \
-e APP_ENV=production \
-p 8181:80 \
--name magellon_ctf_plugin_container \
magellon_ctf_plugin_image

rsync -avz --progress bk22n@hpc-login.rcc.fsu.edu:/gpfs/research/secm4/leginondata/24jun28a/rawdata/ /magellon/gpfs/24jun28a/rawdata/
rsync -avz --progress bk22n@hpc-login.rcc.fsu.edu:/gpfs/research/secm4/leginondata/24jun28a/rawdata/ c:/temp/magellon/gpfs/24jun28a/rawdata/

/rcc_gpfs/research/secm4/leginondata/24jun28a/rawdata/24jun28a_Valle001-01_00003gr.mrc
/gpfs/research/secm4/leginondata/24jun28a/rawdata/24jun28a_Valle001-01_00003gr.mrc
C:\temp\magellon\24jun28a

Y:/research/secm4/leginondata/24jun28a/rawdata/24jun28a_Valle001-01_00003gr.mrc
/gpfs/24jun28a/rawdata/24jun28a_Valle001-01_00003gr.mrc


C:\temp\magellon\24jun28a



ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'behd1d2';
CREATE USER 'behdad'@'%'    IDENTIFIED WITH mysql_native_password BY 'behd1d2';
GRANT ALL PRIVILEGES ON * .* TO 'behdad'@'%';


