https://medium.com/@rajeshshukla_49087/ansible-inventory-file-using-terraform-b305db3ead2


https://blog.gruntwork.io/an-introduction-to-terraform-f17df9c6d180

https://www.percona.com/blog/2021/06/01/how-to-generate-an-ansible-inventory-with-terraform/
## Ansible
ansible -m ping Dbservers
ansible-playbook db.yml — syntax-check



## Template Generation

[cfg]
%{ for index, group in ansible_group_cfg ~}
${ hostname_cfg[index] } ${ index == 0 ? "mongodb_primary=True" : "" }
%{ endfor ~}

%{ for shard_index in number_of_shards ~}
[shard${shard_index}]
%{ for index, group in ansible_group_shards ~}
${ group == tostring(shard_index) && ansible_group_index[index] == "0" ? join(" ", [ hostname_shards[index], "mongodb_primary=True\n" ]) : "" ~}
${ group == tostring(shard_index) && ansible_group_index[index] != "0" ? join("", [ hostname_shards[index], "\n" ]) : "" ~}
%{ endfor ~}
%{ endfor ~}

[mongos]
%{ for index, group in ansible_group_mongos ~}
${hostname_mongos[index]}
%{ endfor ~}
