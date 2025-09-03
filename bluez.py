import dbus
import dbus.mainloop.glib
import dbus.service
import os
import subprocess
import time
from gi.repository import GLib
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

from libraries.bluetooth import constants


class BluetoothDeviceManager:
    """A class for managing Bluetooth devices using the BlueZ D-Bus API."""

    def __init__(self, log=None, interface=None):
        """Initialize the BluetoothDeviceManager by setting up the system bus and adapter.

        Args:
            log: Logger instance.
            interface: Bluetooth adapter interface (e.g., hci0).
        """
        self.bus = dbus.SystemBus()
        self.interface = interface
        self.log = log
        self.adapter_path = f'{constants.bluez_path}/{self.interface}'
        self.adapter_proxy = self.bus.get_object(constants.bluez_service, self.adapter_path)
        self.adapter = dbus.Interface(self.adapter_proxy, constants.adapter_interface)
        self.object_manager = dbus.Interface(self.bus.get_object(constants.bluez_service, "/"), constants.object_manager_interface)
        self.last_session_path = None
        self.opp_process = None
        self.pulseaudio_process = None
        self.stream_process = None

    def get_paired_devices(self):
        """Retrieves all Bluetooth devices that are currently paired with the adapter.

        Returns:
            paired_devices: A dictionary of paired devices.
        """
        paired_devices = {}
        for path, interfaces in self.object_manager.GetManagedObjects().items():
            if constants.device_interface in interfaces:
                device = interfaces[constants.device_interface]
                if device.get("Paired") and device.get("Adapter") == self.adapter_path:
                    address = device.get("Address")
                    name = device.get("Name", "Unknown")
                    paired_devices[address] = name
        return paired_devices

    def start_discovery(self):
        """Start scanning for nearby Bluetooth devices."""
        self.adapter.StartDiscovery()

    def stop_discovery(self):
        """Stop Bluetooth device discovery."""
        self.adapter.StopDiscovery()

    def get_discovered_devices(self):
        """Retrieve discovered Bluetooth devices under the current adapter.

        Returns:
            discovered_devices: A list of discovered Bluetooth devices.
        """
        discovered_devices = []
        for path, interfaces in self.object_manager.GetManagedObjects().items():
            if constants.device_interface in interfaces:
                device = interfaces[constants.device_interface]
                if device.get("Adapter") != self.adapter_path:
                    continue
                try:
                    address = device.get("Address")
                    alias = device.get("Alias", "Unknown")
                    discovered_devices.append({
                        "path":path,
                        "address":address,
                        "alias":alias
                    })
                except Exception as e:
                    if self.log:
                        self.log.warning("Failed to extract device info from %s:%s", path, e)
        return discovered_devices

    def find_device_path(self, address):
        """Find the D-Bus object path of a device by address under the correct adapter.

        Args:
            address: Bluetooth device MAC address.
        Return:
            path: D-Bus object path or None if not found.
        """
        formatted_interface_path = f"{constants.bluez_path}/{self.interface}/"
        for path, interfaces in self.object_manager.GetManagedObjects().items():
            if constants.device_interface in interfaces:
                if formatted_interface_path in path:
                    props = interfaces[constants.device_interface]
                    if props.get("Address") == address:
                        return path
        return None

    def register_agent(self, capability=None):
        """Register this object as a Bluetooth pairing agent."""
        agent_manager = dbus.Interface(self.bus.get_object(constants.bluez_service, constants.bluez_path), constants.agent_interface)
        agent_manager.RegisterAgent(constants.agent_path, capability)
        agent_manager.RequestDefaultAgent(constants.agent_path)
        self.log.info("Registered with capability:%s", capability)

    def pair(self, address):
        """Pairs with a Bluetooth device using the given controller interface.

        Args:
            address: Bluetooth MAC address.
        Return:
             True if successfully paired, False otherwise.
        """
        device_path = self.find_device_path(address)
        if not device_path:
            self.log.info("Device path not found for %s on %s", address, self.interface)
            return False
        try:
            device_proxy = self.bus.get_object(constants.bluez_service, device_path)
            device = dbus.Interface(device_proxy, constants.device_interface)
            properties = dbus.Interface(device_proxy, constants.properties_interface)
            try:
                if properties.Get(constants.device_interface, "Paired"):
                    self.log.info("Device %s is already paired.", address)
                    return True
            except dbus.exceptions.DBusException:
                pass
            self.log.info("Initiating pairing with %s", address)
            device.Pair()
            try:
                paired = properties.Get(constants.device_interface, "Paired")
                if paired:
                    self.log.info("Successfully paired with %s", address)
                    return True
            except dbus.exceptions.DBusException as e:
                self.log.warning("D-Bus error while checking pairing status:%s", e)
            time.sleep(1)
            self.log.warning("Pairing not confirmed with %s within the timeout period.", address)
            return False
        except dbus.exceptions.DBusException as e:
            self.log.error("%s", e)
            return False

    def connect(self, address):
        """Establish a  connection to the specified Bluetooth device.

        Args:
            address: Bluetooth device MAC address.
        Return:
            True if connected, False otherwise.
        """
        device_path = self.find_device_path(address)
        if device_path:
            try:
                device = dbus.Interface(self.bus.get_object(constants.bluez_service, device_path), constants.device_interface)
                device.Connect()
                properties = dbus.Interface(self.bus.get_object(constants.bluez_service, device_path), constants.properties_interface)
                connected = properties.Get(constants.device_interface, "Connected")
                if connected:
                    self.log.info("Connection successful to %s", address)
                    return True
            except Exception as e:
                self.log.info("Connection failed:%s", e)
                return False
        else:
            self.log.info("Device path not found for address %s", address)
            return False

    def disconnect(self, address):
        """Disconnect a Bluetooth  device from the specified adapter.

        Args:
            address: Bluetooth MAC address of the device.
        Return:
            True if disconnected or already disconnected, False if an error occurred.
        """
        device_path = self.find_device_path(address)
        if device_path:
            try:
                device = dbus.Interface(self.bus.get_object(constants.bluez_service, device_path), constants.device_interface)
                props = dbus.Interface(self.bus.get_object(constants.bluez_service, device_path), constants.properties_interface)
                connected = props.Get(constants.device_interface, "Connected")
                if not connected:
                    self.log.info("Device %s is already disconnected.", address)
                    return True
                device.Disconnect()
                return True
            except dbus.exceptions.DBusException as e:
                self.log.info("Error disconnecting device %s:%s", address, e)
        return False

    def remove_device(self, address):
        """Removes a paired or known Bluetooth device from the system using BlueZ D-Bus.

        Args:
            address: The Bluetooth MAC address of the device to remove.
        Returns:
            True if the device was removed successfully or already not present,
            False if the removal failed or the device still exists afterward.
        """
        try:
            target_path = None
            for path, interfaces in self.object_manager.GetManagedObjects().items():
                if constants.device_interface in interfaces:
                    if interfaces[constants.device_interface].get("Address") == address and path.startswith(self.adapter_path):
                        target_path = path
                        break
            if not target_path:
                self.log.info("Device with address %s not found on %s", address, self.interface)
                return True
            self.adapter.RemoveDevice(target_path)
            self.log.info("Requested removal of device %s at path %s", address, target_path)
            time.sleep(0.5)
            self.log.info("Device %s removed successfully", address)
            return True
        except dbus.exceptions.DBusException as e:
            self.log.error("DBusException while removing device %s:%s", address, e)
            return False

    def is_device_paired(self, device_address):
        """Checks if the specified device is paired.
        Args:
            device_address: Bluetooth MAC address.
        Returns:
            True if paired, False otherwise.
        """
        device_path = self.find_device_path(device_address)
        if not device_path:
            return False
        properties = dbus.Interface(self.bus.get_object(constants.bluez_service, device_path), constants.properties_interface)
        try:
            return properties.Get(constants.device_interface, "Paired")
        except dbus.exceptions.DBusException:
            return False

    def is_device_connected(self, device_address):
        """Checks if the specified device is connected.

        Args:
            device_address: Bluetooth MAC address.
        Returns:
            True if connected, False otherwise.
        """
        device_path = self.find_device_path(device_address)
        if not device_path:
            self.log.debug("Device path not found for %s on %s", device_address, self.interface)
            return False
        try:
            properties = dbus.Interface(self.bus.get_object(constants.bluez_service, device_path), constants.properties_interface)
            connected = properties.Get(constants.device_interface, "Connected")
            if self.interface not in device_path:
                self.log.debug("Device path %s does not match interface %s", device_path, self.interface)
                return False
            return connected
        except dbus.exceptions.DBusException as e:
            self.log.debug("DBusException while checking connection:%s", e)
            return False

    def start_a2dp_stream(self, address, filepath=None):
        """Initiates an A2DP audio stream to a Bluetooth device using PulseAudio.

        Args:
            address: Bluetooth MAC address of the target device.
            filepath: Path to the audio file.
        Returns:
            True if the stream was started, False otherwise.
        """
        device_path = self.find_device_path(address)
        self.log.info("Device path : %s",device_path)
        if not device_path:
            return None
        try:
            if not filepath or not os.path.exists(filepath):
                self.log.warning("File path %s does not exist", filepath)
            self.log.info("Starting stream with %s", filepath)
            self.stream_process = subprocess.Popen(["paplay", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            self.log.error("Stream error : %s", e)
            return False

    def stop_a2dp_stream(self):
        """Stop the current A2DP audio stream

        Returns:
            True if the stream was stopped, False otherwise.
        """
        if hasattr(self, 'stream_process') and self.stream_process:
            self.stream_process.terminate()
            self.stream_process = None
            self.log.info("Stream stopped")
            return True
        return False

    def media_control(self, command, address=None):
        """Sends AVRCP (Audio/Video Remote Control Profile) media control commands to a connected Bluetooth device.

        Args:
            command: The AVRCP command to send. Must be one of: "play", "pause", "next", "previous", "rewind".
            address: Bluetooth MAC address of the target device.
        """
        valid = {"play" : "Play", "pause" : "Pause", "next" : "Next", "previous" : "Previous", "rewind" : "Rewind"}
        if command not in valid:
            self.log.info("Invalid media control command:%s", command)
        media_control_interface = self.get_media_control_interface(address)
        if not media_control_interface:
            self.log.info(" MediaControl1 interface NOT FOUND")
        self.log.info(" MediaControl1 interface FOUND")
        try:
            getattr(media_control_interface, valid[command])()
            self.log.info("AVRCP %s sent successfully to %s", command, address)
        except Exception as e:
            self.log.warning("AVRCP command %s failed with exception : %s", command, e)

    def get_media_control_interface(self, address):
        """Retrieve the `org.bluez.MediaControl1` D-Bus interface for a given Bluetooth device.

        Args:
            address: The MAC address of the target Bluetooth device.
        Returns:
            The MediaControl1 D-Bus interface if found, otherwise None.
        """
        try:
            formatted_addr = address.replace(":", "_").upper()
            for path, interfaces in self.object_manager.GetManagedObjects().items():
                if constants.media_control_interface in interfaces:
                    if formatted_addr in path and path.startswith(self.adapter_path):
                        self.log.info("Found MediaControl1 at %s", path)
                        return dbus.Interface(self.bus.get_object(constants.bluez_service, path), constants.media_control_interface)
            self.log.info(" No MediaControl1 interface found for %s under %s", address, self.adapter_path)
        except Exception as e:
            self.log.info(" Exception while getting MediaControl1 interface : %s", e)
        return None

    def get_connected_a2dp_devices_by_role(self, role):
        """Get a dictionary of currently connected A2DP devices by role (source or sink).

        Args:
            role: Either "source" or "sink"
        Returns:
            connected_a2dp_devices: Dictionary of connected A2DP devices.
        """
        uuid_map = {"source":"110a", "sink":"110b"}
        if role not in uuid_map:
            self.log.warning("Unknown role %s", role)
        target_uuid = uuid_map[role]
        connected_a2dp_devices = {}
        for path, interfaces in self.object_manager.GetManagedObjects().items():
            if constants.device_interface in interfaces:
                properties = interfaces[constants.device_interface]
                if properties.get("Connected") and properties.get("Adapter") == self.adapter_path:
                    uuids = properties.get("UUIDs", [])
                    if any(target_uuid in uuid.lower() for uuid in uuids):
                        address = properties.get("Address")
                        name = properties.get("Name", "Unknown")
                        connected_a2dp_devices[address] = name
        return connected_a2dp_devices

    def send_file(self, device_address, file_path):
        """Send a file using OPP and wait for real-time transfer status."""
        if not os.path.exists(file_path):
            self.log.info("File does not exist: %s", file_path)
            return "error"
        try:
            bus = dbus.SessionBus()
            obex_manager = dbus.Interface(bus.get_object(constants.obex_service, constants.obex_path), constants.obex_client)
            if getattr(self, "last_session_path", None):
                try:
                    obex_manager.RemoveSession(self.last_session_path)
                    self.log.info("Removed previous OBEX session: %s", self.last_session_path)
                except Exception as e:
                    self.log.info("Failed to remove previous OBEX session: %s", e)
                finally:
                    self.last_session_path = None
            session_path = obex_manager.CreateSession(device_address, {"Target": dbus.String("opp")})
            self.last_session_path = session_path
            self.log.info(f"Created OBEX session : {session_path}")
            opp_interface= dbus.Interface(bus.get_object(constants.obex_service, session_path), constants.obex_object_push)
            transfer_path, _ = opp_interface.SendFile(file_path)
            self.log.info("Started transfer: %s", transfer_path)
            self.transfer_status = {"status": "unknown"}
            bus.add_signal_receiver(
                self.obex_properties_changed,
                dbus_interface = constants.properties_interface,
                signal_name = "PropertiesChanged",
                arg0 = constants.obex_object_transfer,
                path = transfer_path,
                path_keyword = "path"
            )
            self.transfer_loop = GLib.MainLoop()
            GLib.timeout_add_seconds(10, self.transfer_loop.quit)
            self.transfer_loop.run()
            status = self.transfer_status["status"]
            try:
                obex_manager.RemoveSession(session_path)
                self.log.info("Removed OBEX session after transfer: %s", session_path)
                self.last_session_path = None
            except Exception as e:
                self.log.info("Error removing OBEX session:%s", e)
            return status
        except Exception as e:
            self.log.info("OBEX signal-based send failed:%s", e)
            return "error"

    def obex_properties_changed(self, interface, changed, invalidated, path):
        if "Status" in changed:
            status = str(changed["Status"])
            self.log.info("Signal: Transfer status changed to:%s",status)
            self.transfer_status["status"] = status
            if hasattr(self, "transfer_loop") and self.transfer_loop.is_running():
                self.transfer_loop.quit()

    '''def receive_file(self, save_directory = "/tmp", timeout = 60):
        """Start an OBEX Object Push server and wait for a file to be received."""
        try:
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)
            subprocess.run(["killall", "-9", "obexpushd"], check=False)
            self.log.info("Killed existing obexpushd processes (if any).")
            existing_files = set(os.listdir(save_directory))
            self.opp_process = subprocess.Popen(["obexpushd", "-B", "-o", save_directory, "-n"])
            self.log.info("OPP server started. Waiting for incoming file...")
            start_time = time.time()
            while time.time() - start_time < timeout:
                current_files = set(os.listdir(save_directory))
                new_files = current_files - existing_files
                if new_files:
                    received_file = new_files.pop()
                    self.log.info("Received file: %s", received_file)
                    self.stop_opp_receiver()
                    return os.path.join(save_directory, received_file)
                time.sleep(1)
            self.log.info("No file received within timeout.")
            return None
        except Exception as e:
            self.log.info("Error starting OPP server: %s", e)
            return None'''

    def receive_file(self, save_directory="/tmp", timeout=20, user_confirm_callback=None):
        """Start an OBEX Object Push server and wait for a file to be received."""
        try:
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)
            subprocess.run(["killall", "-9", "obexpushd"], check=False)
            self.log.info("Killed existing obexpushd processes..")
            existing_files = set(os.listdir(save_directory))
            self.opp_process = subprocess.Popen(["obexpushd", "-B", "-o", save_directory, "-n"])
            self.log.info("OPP server started. Waiting for incoming file...")
            start_time = time.time()
            while time.time() - start_time < timeout:
                current_files = set(os.listdir(save_directory))
                new_files = current_files - existing_files
                if new_files:
                    received_file = new_files.pop()
                    full_path = os.path.join(save_directory, received_file)
                    self.log.info("Incoming file:%s", received_file)
                    user_accepted = True
                    if user_confirm_callback:
                        user_accepted = user_confirm_callback(full_path)
                    if user_accepted:
                        self.log.info("User accepted file.")
                        self.stop_opp_receiver()
                        return full_path
                    else:
                        self.log.info("User rejected file.")
                        os.remove(full_path)
                        self.stop_opp_receiver()
                        return None
        except Exception as e:
            self.stop_opp_receiver()
            self.log.info("Error in receive_file: %s", e)
            return None

    def stop_opp_receiver(self):
        """Stop the OBEX Object Push server if it's currently running."""
        if self.opp_process and self.opp_process.poll() is None:
            self.opp_process.terminate()
            self.opp_process.wait()
            self.log.info("OPP server stopped.")

    def get_media_playback_info(self, address):
        """Retrieve playback status, track info, and position using MediaPlayer1.

        Args:
            address: MAC address of the Bluetooth sink device.

        Returns:
             status, track, position (ms), duration (ms), or None if unavailable.
        """
        try:
            formatted_addr = address.replace(":", "_").upper()
            for path, interfaces in self.object_manager.GetManagedObjects().items():
                if constants.media_player_interface in interfaces:
                    if formatted_addr in path and path.startswith(self.adapter_path):
                        media_player = dbus.Interface(self.bus.get_object(constants.bluez_service, path),
                                                      constants.media_player_interface)
                        props = dbus.Interface(media_player, constants.properties_interface)
                        status = props.Get(constants.media_player_interface, "Status")
                        track = props.Get(constants.media_player_interface, "Track")
                        position = props.Get(constants.media_player_interface, "Position")
                        duration = track.get("Duration", 0)
                        return {
                            "status": str(status),
                            "track": {
                                "title": str(track.get("Title", "")),
                                "artist": str(track.get("Artist", "")),
                                "album": str(track.get("Album", "")),
                            },
                            "position": int(position),
                            "duration": int(duration)
                        }
        except Exception as e:
            self.log.warning("Failed to get media playback info: %s", e)
        return None

    def get_media_volume(self, address):
        """Get the current A2DP volume for the given device."""
        try:
            formatted_addr = address.replace(":", "_").upper()
            for path, interfaces in self.object_manager.GetManagedObjects().items():
                if constants.media_transport_interface in interfaces:
                    if formatted_addr in path and path.startswith(self.adapter_path):
                        transport = dbus.Interface(self.bus.get_object(constants.bluez_service, path),
                                                   constants.properties_interface)
                        volume = transport.Get(constants.media_transport_interface, "Volume")
                        return int(volume)
        except Exception as e:
            self.log.warning("Failed to get volume: %s", e)
        return None

    def set_media_volume(self, address, volume):
        """Set A2DP volume (0–127) for the given device."""
        try:
            formatted_addr = address.replace(":", "_").upper()
            for path, interfaces in self.object_manager.GetManagedObjects().items():
                if constants.media_transport_interface in interfaces:
                    if formatted_addr in path and path.startswith(self.adapter_path):
                        transport = dbus.Interface(self.bus.get_object(constants.bluez_service, path),
                                                   constants.properties_interface)
                        transport.Set(constants.media_transport_interface, "Volume", dbus.UInt16(volume))
                        self.log.info("Volume set to %d", volume)
                        return True
        except Exception as e:
            self.log.warning("Failed to set volume: %s", e)
        return False

