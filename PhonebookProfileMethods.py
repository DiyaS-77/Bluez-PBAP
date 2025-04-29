import dbus
import time


class PhoneBookAccess:
    def __init__(self, device_address):
        self.device_address = device_address
        self.bus = dbus.SessionBus()
        self.client = dbus.Interface(self.bus.get_object("org.bluez.obex", "/org/bluez/obex"), "org.bluez.obex.Client1")
        self.session_path = None
        self.phonebook = None

    def create_session(self):
        args = {"Target": dbus.String("PBAP", variant_level=1)}
        self.session_path = self.client.CreateSession(self.device_address, args)
        print(f" Session created at: {self.session_path}")

        time.sleep(1)

        self.phonebook = dbus.Interface(
            self.bus.get_object("org.bluez.obex", self.session_path),
            "org.bluez.obex.PhonebookAccess1")

    def select_phonebook(self, location, folder):
        if not self.phonebook:
            print(" Phonebook interface not initialized.")
            return
        self.phonebook.Select(location,folder)
        print(f"Selected {location}/{folder} phonebook.")

    def get_size(self):
        if self.phonebook:
            size = self.phonebook.GetSize()
            print(f"Phonebook size: {size}")
        else:
            print(" Phonebook interface not ready.")
    
    def list_filters(self):
        fields = self.phonebook.ListFilterFields()
        print("Available Filter Fields:")
        for field in fields:
            if not field.startswith("BIT"):
                print(f" - {field}")

    def list_contacts(self):

        contacts = self.phonebook.List({})
        for vcard, name in contacts:
            print(f"{vcard} - {name}")

    def pull(self, vcard_handle, target_file="/tmp/single.vcf"):
        print(f"Pulling vCard: {vcard_handle} to {target_file}")
        transfer_path, props = self.phonebook.Pull(vcard_handle, target_file, {})
        print(f" Pulled {vcard_handle} to {target_file}")
    
    def pull_all(self, target_file="/tmp/pb.vcf"):
        print(" Pulling full phonebook...")
        transfer_obj, transfer_props = self.phonebook.PullAll(target_file, {})
        print(f" PullAll complete. File saved: {target_file}")

    def search_contacts(self, search_field, search_value):
        print(f"Searching contacts by {search_field}: {search_value}")
        results = self.phonebook.Search(search_field, search_value, {})
        for vcard, search_field in results:
            print(f"Found: {vcard} - {search_field}")

    def disconnect(self):
        if self.session_path:
            self.client.RemoveSession(self.session_path)
            print("Session removed.")
            self.session_path = None

    def get_property(self, prop_name):
        props_iface = dbus.Interface(
        self.bus.get_object("org.bluez.obex", self.session_path),
        "org.freedesktop.DBus.Properties"
         )
  
        try:
            value = props_iface.Get("org.bluez.obex.PhonebookAccess1", prop_name)
            print(f"{prop_name} = {value}")
        except dbus.exceptions.DBusException as e:
            print(f" Error: {prop_name} not found or unsupported.\n{e}")
        

