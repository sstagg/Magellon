from core.model_dto import PluginInfoSingleton

plugin_info_data = {
    "id": "29105843-518a-4086-b802-ad295883dfe1",
    "name": "CTF Plugin",
    "developer": "Behdad Khoshbin b.khoshbin@gmail.com",
    "copyright": "Copyright © 2024",
    "version": "1.0.2",
    "port_number": 8000
}


def get_plugin_info():
    return PluginInfoSingleton.get_instance(**plugin_info_data)
