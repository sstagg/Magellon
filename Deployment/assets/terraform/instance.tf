resource "hcloud_server" "server" {                     # Create a server
  name = "server-${local.name}"                         # Name server
  image = "${var.image}"                                # Basic image
  server_type = "${var.server_type}"                    # Instance type
  location = "${var.location}"                          # Region
  backups = "false"                                     # Enable backups
  ssh_keys =  ["${hcloud_ssh_key.user.id}"]      # ["${data.hcloud_ssh_key.ssh_key.id}"]
  user_data = "${data.template_file.instance.rendered}" # The script that works when you start

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  connection {
    type = "ssh"
    user = "root"
    #      private_key = "${file(var.private_key_path)}"
    private_key = "${file("~/.ssh/id_rsa")}"
    host = "${self.ipv4_address}"
  }


  provisioner "file" {                                  # Copying files to instances
    source = "user-data/setup.sh"                           # Path to file on local machine
    destination = "/root/setup.sh"                          # Path to copy
  }
  provisioner "file" {                                  # Copying files to instances
    source = "user-data/file"                           # Path to file on local machine
    destination = "/root/file"                          # Path to copy
  }
  provisioner "remote-exec" {
    inline = [
      "apt update",
      "apt-get install wget build-essential libreadline-dev libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev -y",
      "apt update",
      "apt install -y python3 python3-pip"
    ]
  }
}

# File definition user-data
data "template_file" "instance" {
  template = "${file("${path.module}/user-data/instance.tpl")}"
}

# Definition ssh key from variable
resource "hcloud_ssh_key" "user" {
  name = "user"
  public_key = "${var.public_key}"
}

# Generate inventory file
resource "local_file" "inventory" {
  filename = "./ansible/hosts.ini"
  content = <<EOF
  [webserver]
  ${hcloud_server.server.ipv4_address}
  ${hcloud_server.server.ipv4_address}
  [dbserver]
  ${hcloud_server.server.ipv4_address}
EOF
}