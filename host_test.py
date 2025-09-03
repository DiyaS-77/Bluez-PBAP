import os
import re

from PyQt6.QtCore import Qt
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import QComboBox, QSlider
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QGridLayout
from PyQt6.QtWidgets import QGroupBox
from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLayout
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QSizePolicy
from PyQt6.QtWidgets import QTabWidget
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

import style_sheet as styles
from libraries.bluetooth.bluez import BluetoothDeviceManager
from libraries.bluetooth import constants
from Utils.utils import get_controller_interface_details
from Utils.utils import start_dump_logs


class TestApplication(QWidget):
    """Main GUI class for the Bluetooth Test Host."""

    def __init__(self, interface=None, back_callback=None, log=None):
        """Initialize the Test Host widget.

        Args:
            interface: Bluetooth adapter interface (e.g., hci0).
            back_callback: Optional callback to trigger on back action.
            log: Logger instance.
        """
        super().__init__()
        self.profile_methods_layout = None
        self.profile_methods_layout = None
        self.back_callback = back_callback
        self.interface = interface
        self.log_path = log.log_path
        self.log = log
        self.bluetooth_device_manager = BluetoothDeviceManager(log=self.log, interface=self.interface)
        self.paired_devices={}
        self.device_tab_widget = None
        self.gap_button = None
        self.grid = None
        self.hcidump_log_name = None
        self.main_grid_layout = None
        self.profile_description_text_browser = None
        self.profile_methods_widget = None
        self.profiles_list_widget = None
        self.refresh_button = None
        self.test_application_clicked()

    def populate_device_list(self):
        """Loads and displays all paired  Bluetooth devices into the profiles list widget."""
        list_index = self.profiles_list_widget.count() - 1
        self.paired_devices = self.bluetooth_device_manager.get_paired_devices()
        unique_devices = set(self.paired_devices.keys())
        for device_address in unique_devices:
            device_item = QListWidgetItem(device_address)
            device_item.setFont(QFont("Courier New", 10))
            device_item.setForeground(Qt.GlobalColor.black)
            list_index += 1
            self.profiles_list_widget.insertItem(list_index, device_item)

    def add_row(self, row, label, value):
        """Adds a new row to the controller details grid layout.

        Args:
            row: The row index in the grid layout where this entry should be placed.
            label: The text label to describe the data.
            value: The corresponding value to display alongside the label.
        """
        label_widget = QLabel(label)
        label_widget.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        label_widget.setStyleSheet("color:#000000;")
        value_widget = QLabel(value)
        value_widget.setFont(QFont("Arial", 10))
        value_widget.setStyleSheet("color:#000000;")
        self.grid.addWidget(label_widget, row, 0)
        self.grid.addWidget(value_widget, row, 1)

    def is_bluetooth_address(self, address):
        """Validates whether the given string is a Bluetooth MAC address.

        Args:
            address: The string to be validated.
        Returns:
            True if valid Bluetooth address, False otherwise.
        """
        pattern = r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$'
        return bool(re.fullmatch(pattern, address))

    def set_discoverable_on(self):
        """Set the local Bluetooth device to discoverable mode."""
        self.log.info("Discoverable is set to ON")
        self.set_discoverable_on_button.setEnabled(False)
        self.set_discoverable_off_button.setEnabled(True)
        self.bluetooth_device_manager.set_discoverable_on()
        timeout = int(self.discoverable_timeout_input.text())
        if timeout > 0:
            self.discoverable_timeout_timer = QTimer()
            self.discoverable_timeout_timer.timeout.connect(self.set_discoverable_off)
            self.discoverable_timeout_timer.start(timeout * 1000)

    def set_discoverable_off(self):
        """Disable discoverable mode on the Bluetooth adapter."""
        self.log.info("Discoverable is set to OFF")
        self.set_discoverable_on_button.setEnabled(True)
        self.set_discoverable_off_button.setEnabled(False)
        self.bluetooth_device_manager.set_discoverable_off()
        if hasattr(self, 'discoverable_timeout_timer'):
            self.discoverable_timeout_timer.stop()

    def set_discovery_on(self):
        """Start device discovery."""
        self.log.info("Discovery has started")
        self.inquiry_timeout = int(self.inquiry_timeout_input.text()) * 1000
        if self.inquiry_timeout == 0:
            self.set_discovery_on_button.setEnabled(False)
            self.set_discovery_off_button.setEnabled(True)
            self.bluetooth_device_manager.start_discovery()
        else:
            self.timer = QTimer()
            self.timer.timeout.connect(self.show_discovery_table_timeout)
            self.timer.timeout.connect(lambda: self.set_discovery_off_button.setEnabled(False))
            self.timer.start(self.inquiry_timeout)
            self.set_discovery_on_button.setEnabled(False)
            self.set_discovery_off_button.setEnabled(True)
            self.bluetooth_device_manager.start_discovery()

    def show_discovery_table_timeout(self):
        """Function to show the discovery table when timeout is over"""
        self.timer.stop()
        self.bluetooth_device_manager.stop_discovery()
        self.show_discovery_table()

    def set_discovery_off(self):
        """Function for Stop Discovery"""
        self.log.info("Discovery has stopped")
        self.set_discovery_off_button.setEnabled(False)
        self.timer = QTimer()
        if self.inquiry_timeout == 0:
            self.bluetooth_device_manager.stop_discovery()
            self.show_discovery_table()
        else:
            self.timer.stop()
            self.bluetooth_device_manager.stop_discovery()
            self.show_discovery_table()
            self.set_discovery_off_button.setEnabled(False)

    def show_discovery_table(self):
        """Display discovered devices in a table with options to pair or connect."""
        self.timer.stop()
        bold_font = QFont()
        bold_font.setBold(True)
        small_font = QFont()
        small_font.setBold(True)
        small_font.setPointSize(8)
        discovered_devices = self.bluetooth_device_manager.get_discovered_devices()
        self.clear_discovery_table_widgets()
        self.table_widget = QTableWidget(0, 3)
        self.table_widget.setHorizontalHeaderLabels(["DEVICE NAME", "BD_ADDR", "PROCEDURES"])
        self.table_widget.setFont(bold_font)
        header = self.table_widget.horizontalHeader()
        header.setStyleSheet(styles.horizontal_header_style_sheet)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        vertical_header = self.table_widget.verticalHeader()
        vertical_header.setStyleSheet(styles.vertical_header_style_sheet)
        row = 0
        for device in discovered_devices:
            device_address = device["address"]
            device_name = device["alias"]
            self.table_widget.insertRow(row)
            self.table_widget.setItem(row, 0, QTableWidgetItem(device_name))
            self.table_widget.setItem(row, 1, QTableWidgetItem(device_address))
            button_widget = QWidget()
            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(0, 0, 0, 0)
            button_layout.setSpacing(5)
            pair_button = QPushButton("PAIR")
            pair_button.setFont(small_font)
            pair_button.clicked.connect(lambda _, addr = device_address: self.manage_device('pair', addr, load_profiles=False))
            button_layout.addWidget(pair_button)
            connect_button = QPushButton("CONNECT")
            connect_button.setFont(small_font)
            connect_button.clicked.connect(lambda _, addr = device_address: self.manage_device('connect', addr, load_profiles=False))
            button_layout.addWidget(connect_button)
            button_widget.setLayout(button_layout)
            self.table_widget.setCellWidget(row, 2, button_widget)
            row += 1
        self.profile_methods_layout.insertWidget(self.profile_methods_layout.count() - 1, self.table_widget)
        self.table_widget.show()
        self.set_discovery_off_button.setEnabled(False)

    def clear_discovery_table_widgets(self):
        """Removes the discovery table if it exists to avoid stacking."""
        if hasattr(self, 'table_widget') and self.table_widget:
            self.profile_methods_layout.removeWidget(self.table_widget)
            self.table_widget.deleteLater()
            self.table_widget = None

    def refresh(self):
        """Refresh and clear the device discovery table."""
        self.log.info("Refresh Button is pressed")
        if hasattr(self, 'table_widget') and self.table_widget:
            self.profile_methods_layout.removeWidget(self.table_widget)
            self.table_widget.deleteLater()
            self.table_widget = None
            self.inquiry_timeout_input.setText("0")
            self.refresh_button.setEnabled(False)
            self.set_discovery_on_button.setEnabled(True)
            self.set_discovery_off_button.setEnabled(False)
            self.refresh_button.setEnabled(True)

    def refresh_discoverable(self):
        """Reset discoverable timeout input to default (0)."""
        self.log.info("Discoverable refresh button is pressed")
        self.discoverable_timeout_input.setText("0")

    def add_device(self, device_address):
        """Adds a device address to the profile list if not already present.

        Args:
            device_address: device MAC address
        """
        for i in range(self.profiles_list_widget.count()):
            if self.profiles_list_widget.item(i).text().strip() == device_address:
                return
        device_item = QListWidgetItem(device_address)
        device_item.setFont(QFont("Courier New", 10))
        device_item.setForeground(Qt.GlobalColor.black)
        self.profiles_list_widget.addItem(device_item)

    def clear_layout(self, layout):
        """Delete all widgets and sub-layouts from a layout."""
        if not isinstance(layout, QLayout):
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if child_layout:
                self.clear_layout(child_layout)
            if widget:
                widget.deleteLater()

    def profile_selected(self, profile_name=None):
        """Handles profile selection from either the list or a button."""
        if profile_name is None:
            selected_item = self.profiles_list_widget.currentItem()
            if not selected_item:
                return
            selected_item_text = selected_item.text().strip()
        else:
            selected_item_text = profile_name.strip()
        self.clear_discovery_table_widgets()
        self.clear_layout(self.profile_methods_layout)
        if hasattr(self, 'device_tab_widget') and self.device_tab_widget:
            self.device_tab_widget.currentChanged.disconnect(self.on_profile_tab_changed)
            self.profile_methods_layout.removeWidget(self.device_tab_widget)
            self.device_tab_widget.hide()
            self.device_tab_widget.setParent(None)
            self.device_tab_widget.deleteLater()
            self.device_tab_widget = None
        QTimer.singleShot(0, lambda: (self.load_profile_tabs_for_device(selected_item_text)
        if self.is_bluetooth_address(selected_item_text)else
        self.build_gap_ui() if selected_item_text == "GAP"
        else None))

    def build_gap_ui(self):
        """Build and display the widgets for the GAP profile."""
        bold_font = QFont()
        bold_font.setBold(True)
        self.profile_description_text_browser.setText("GAP Profile Selected\nUse the below methods as required: ")
        label = QLabel("SetDiscoverable:")
        label.setFont(bold_font)
        label.setStyleSheet("color:black; ")
        self.profile_methods_layout.addWidget(label)
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("SetDiscoverable Timeout:")
        timeout_label.setFont(bold_font)
        timeout_label.setStyleSheet("color:blue; ")
        self.discoverable_timeout_input = QLineEdit("0")
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(self.discoverable_timeout_input)
        self.profile_methods_layout.addLayout(timeout_layout)
        buttons_layout = QHBoxLayout()
        self.set_discoverable_on_button = QPushButton("ON")
        self.set_discoverable_on_button.setStyleSheet("color:green;")
        self.set_discoverable_on_button.clicked.connect(self.set_discoverable_on)
        self.set_discoverable_off_button = QPushButton("OFF")
        self.set_discoverable_off_button.setStyleSheet("color:red;")
        self.set_discoverable_off_button.clicked.connect(self.set_discoverable_off)
        self.set_discoverable_off_button.setEnabled(False)
        buttons_layout.addWidget(self.set_discoverable_on_button)
        buttons_layout.addWidget(self.set_discoverable_off_button)
        self.profile_methods_layout.addLayout(buttons_layout)
        self.refresh_button = QPushButton("REFRESH")
        self.refresh_button.setStyleSheet("color:green;")
        self.refresh_button.clicked.connect(self.refresh_discoverable)
        self.profile_methods_layout.addWidget(self.refresh_button)
        inquiry_label = QLabel("Inquiry:")
        inquiry_label.setFont(bold_font)
        inquiry_label.setStyleSheet("color:black;")
        self.profile_methods_layout.addWidget(inquiry_label)
        inquiry_timeout_layout = QHBoxLayout()
        inquiry_timeout_label = QLabel("Inquiry Timeout:")
        inquiry_timeout_label.setFont(bold_font)
        inquiry_timeout_label.setStyleSheet("color:blue;")
        self.inquiry_timeout_input = QLineEdit("0")
        inquiry_timeout_layout.addWidget(inquiry_timeout_label)
        inquiry_timeout_layout.addWidget(self.inquiry_timeout_input)
        self.profile_methods_layout.addLayout(inquiry_timeout_layout)
        discovery_buttons_layout = QHBoxLayout()
        self.set_discovery_on_button = QPushButton("START")
        self.set_discovery_on_button.setStyleSheet("color:green;")
        self.set_discovery_on_button.clicked.connect(self.set_discovery_on)
        self.set_discovery_off_button = QPushButton("STOP")
        self.set_discovery_off_button.setStyleSheet("color:red;")
        self.set_discovery_off_button.clicked.connect(self.set_discovery_off)
        self.set_discovery_off_button.setEnabled(False)
        discovery_buttons_layout.addWidget(self.set_discovery_on_button)
        discovery_buttons_layout.addWidget(self.set_discovery_off_button)
        self.profile_methods_layout.addLayout(discovery_buttons_layout)
        capability_label = QLabel("Select Capability:")
        capability_label.setFont(bold_font)
        self.capability_combobox = QComboBox()
        self.capability_combobox.setFont(QFont("Arial", 10))
        self.capability_combobox.addItems(["DisplayOnly", "DisplayYesNo", "KeyboardOnly", "NoInputNoOutput", "KeyboardDisplay"])
        self.capability_combobox.setCurrentText("NoInputNoOutput")
        register_agent_button = QPushButton("Register Agent")
        register_agent_button.setFont(bold_font)
        register_agent_button.setStyleSheet("color:blue;")
        register_agent_button.clicked.connect(self.register_agent_clicked)
        self.profile_methods_layout.addWidget(capability_label)
        self.profile_methods_layout.addWidget(self.capability_combobox)
        self.profile_methods_layout.addWidget(register_agent_button)
        final_refresh_button = QPushButton("REFRESH")
        final_refresh_button.setStyleSheet("color:green;")
        final_refresh_button.clicked.connect(self.refresh)
        self.profile_methods_layout.addWidget(final_refresh_button)
        self.profile_methods_layout.addStretch(1)

    def start_playback_polling(self):
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.update_media_feedback)
        self.playback_timer.start(1000)  # Poll every second

    '''def update_media_feedback(self):
        info = self.bluetooth_device_manager.get_media_playback_info(self.device_address_sink)
        if not info:
            self.track_status_label.setText("Status: Unknown")
            return
        status = info["status"]
        track = info["track"]
        position = info["position"] // 1000
        duration = info["duration"] // 1000  # in seconds
        title = track.get("title", "Unknown")
        artist = track.get("artist", "")
        self.track_status_label.setText(f"{status}: {title} - {artist} ")
        self.progress_slider.setEnabled(True)
        self.progress_slider.setMaximum(duration)
        self.progress_slider.setValue(position)'''

    def update_media_feedback(self):
        info = self.bluetooth_device_manager.get_media_playback_info(self.device_address_sink)
        if not info:
            self.track_status_label.setText("Status: Unknown")
            self.song_title_label.setText("Title: Unknown")
            self.song_artist_label.setText("Artist: -")
            self.song_album_label.setText("Album: -")
            self.progress_slider.setEnabled(False)
            self.progress_slider.setValue(0)
            self.elapsed_time_label.setText("00:00")
            self.remaining_time_label.setText("00:00")
            return

        # Extract info
        status = info["status"]
        track = info["track"]
        position = info["position"] // 1000  # in seconds
        duration = info["duration"] // 1000  # in seconds

        # Set media labels
        title = track.get("title", "Unknown")
        artist = track.get("artist", "-")
        album = track.get("album", "-")

        self.track_status_label.setText(f"Status: {status}")
        self.song_title_label.setText(f"Title: {title}")
        self.song_artist_label.setText(f"Artist: {artist}")
        self.song_album_label.setText(f"Album: {album}")

        # Update slider and time labels
        self.progress_slider.setEnabled(True)
        self.progress_slider.setMaximum(duration)
        self.progress_slider.setValue(position)

        # Format time mm:ss
        def format_time(secs):
            mins = secs // 60
            sec = secs % 60
            return f"{mins:02}:{sec:02}"

        self.elapsed_time_label.setText(format_time(position))
        self.remaining_time_label.setText(format_time(duration - position))

    def sync_volume_slider(self):
        volume = self.bluetooth_device_manager.get_media_volume(self.device_address_sink)
        if volume is not None:
            self.volume_slider.setValue(volume)

    def set_device_volume(self, value):
        self.bluetooth_device_manager.set_media_volume(self.device_address_sink, value)

    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QLineEdit,
        QGroupBox
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont

    def build_a2dp_ui(self, device_address):
        bold_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        self.device_address_source = device_address
        self.device_address_sink = device_address
        role = self.get_a2dp_role_for_device(device_address)
        print(f"[DEBUG] A2DP role for {device_address}: {role}")
        if role in ["source", "both"]:
            media_control_group = QGroupBox("Media Control (A2DP Sink)")
            media_control_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
            media_control_layout = QVBoxLayout()
            media_control_layout.setSpacing(12)
            self.song_title_label = QLabel("Title: Unknown")
            self.song_artist_label = QLabel("Artist: -")
            self.song_album_label = QLabel("Album: -")
            for label in [self.song_title_label, self.song_artist_label, self.song_album_label]:
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            media_info_layout = QVBoxLayout()
            media_info_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            media_info_layout.addWidget(self.song_title_label)
            media_info_layout.addWidget(self.song_artist_label)
            media_info_layout.addWidget(self.song_album_label)
            media_control_layout.addLayout(media_info_layout)
            control_buttons = QHBoxLayout()
            self.play_button = QPushButton("Play")
            self.pause_button = QPushButton("Pause")
            self.next_button = QPushButton("Next")
            self.previous_button = QPushButton("Previous")
            self.rewind_button = QPushButton("Rewind")
            for btn, action in [
                (self.play_button, "play"),
                (self.pause_button, "pause"),
                (self.next_button, "next"),
                (self.previous_button, "previous"),
                (self.rewind_button, "rewind")
            ]:
                btn.setStyleSheet(styles.bluetooth_profiles_button_style)
                btn.setFont(bold_font)
                btn.clicked.connect(lambda _, a=action: self.media_control(a))
                control_buttons.addWidget(btn)
            media_control_layout.addLayout(control_buttons)
            self.track_status_label = QLabel("Status: -")
            self.track_status_label.setFont(QFont("Segoe UI", 9))
            self.track_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            media_control_layout.addWidget(self.track_status_label)
            self.progress_slider = QSlider(Qt.Orientation.Horizontal)
            self.progress_slider.setRange(0, 100)
            self.progress_slider.setEnabled(False)
            media_control_layout.addWidget(self.progress_slider)
            progress_time_layout = QHBoxLayout()
            self.elapsed_time_label = QLabel("00:00")
            self.remaining_time_label = QLabel("00:00")
            progress_time_layout.addWidget(self.elapsed_time_label)
            progress_time_layout.addStretch()
            progress_time_layout.addWidget(self.remaining_time_label)
            media_control_layout.addLayout(progress_time_layout)
            volume_layout = QHBoxLayout()
            volume_label = QLabel("Volume:")
            volume_label.setFont(bold_font)
            volume_layout.addWidget(volume_label)
            self.volume_slider = QSlider(Qt.Orientation.Horizontal)
            self.volume_slider.setRange(0, 127)
            self.volume_slider.setFixedWidth(150)
            self.volume_slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    border: 1px solid #bbb;
                    background: #eee;
                    height: 10px;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: #5cacee;
                    border: 1px solid #5cacee;
                    width: 18px;
                    margin: -5px 0;
                    border-radius: 9px;
                }
            """)
            self.volume_slider.setEnabled(True)
            self.volume_slider.valueChanged.connect(self.set_device_volume)
            self.volume_value_label = QLabel("100%")
            self.volume_slider.valueChanged.connect(
                lambda v: self.volume_value_label.setText(f"{int(v / 127 * 100)}%"))
            #self.mute_button = QPushButton("Mute")
            #self.mute_button.setCheckable(True)
            #self.mute_button.setStyleSheet("background-color: #E53935; color: white;")
            #self.mute_button.toggled.connect(self.toggle_mute)
            volume_layout.addWidget(self.volume_slider)
            volume_layout.addWidget(self.volume_value_label)
            #volume_layout.addWidget(self.mute_button)
            media_control_layout.addLayout(volume_layout)
            media_control_group.setLayout(media_control_layout)
            layout.addWidget(media_control_group)
            self.sync_volume_slider()
            self.start_playback_polling()
        if role in ["sink", "both"]:
            streaming_group = QGroupBox("Streaming Audio (A2DP Source)")
            streaming_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)

            streaming_layout = QVBoxLayout()
            streaming_layout.setSpacing(10)
            streaming_layout.setContentsMargins(10, 10, 10, 10)

            audio_layout = QHBoxLayout()
            audio_label = QLabel("Audio File:")
            audio_label.setFont(bold_font)
            audio_layout.addWidget(audio_label)

            self.audio_location_input = QLineEdit()
            self.audio_location_input.setReadOnly(True)
            self.audio_location_input.setFixedHeight(28)
            audio_layout.addWidget(self.audio_location_input)

            self.browse_audio_button = QPushButton("Browse...")
            self.browse_audio_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.browse_audio_button.clicked.connect(self.browse_audio_file)
            audio_layout.addWidget(self.browse_audio_button)

            streaming_layout.addLayout(audio_layout)

            streaming_buttons_layout = QHBoxLayout()
            self.start_streaming_button = QPushButton("Start Streaming")
            self.start_streaming_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.start_streaming_button.clicked.connect(self.start_streaming)

            self.stop_streaming_button = QPushButton("Stop Streaming")
            self.stop_streaming_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.stop_streaming_button.clicked.connect(self.stop_streaming)
            self.stop_streaming_button.setEnabled(False)

            streaming_buttons_layout.addWidget(self.start_streaming_button)
            streaming_buttons_layout.addWidget(self.stop_streaming_button)

            streaming_layout.addLayout(streaming_buttons_layout)

            streaming_group.setLayout(streaming_layout)
            layout.addWidget(streaming_group)

        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def toggle_mute(self, muted):
        if muted:
            self.previous_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)
        else:
            self.volume_slider.setValue(self.previous_volume)

    '''def build_a2dp_ui(self, device_address):
        """Builds a single A2DP panel combining source streaming and sink media control,based on the device's A2DP roles.

        Args:
            device_address : The Bluetooth address of the device for which the A2DP tab is built.
        Returns:
            A fully configured QWidget containing the A2DP UI components.
        """
        bold_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        a2dp_label = QLabel("<b>A2DP Functionality</b>")
        a2dp_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        a2dp_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(a2dp_label)
        self.device_address_source = device_address
        self.device_address_sink = device_address
        role = self.get_a2dp_role_for_device(device_address)
        if role in ["sink", "both"]:
            streaming_group = QGroupBox("Streaming Audio (A2DP Source)")
            streaming_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
            streaming_layout = QVBoxLayout()
            streaming_layout.setSpacing(10)
            streaming_layout.setContentsMargins(10, 10, 10, 10)
            audio_layout = QHBoxLayout()
            audio_label = QLabel("Audio File : ")
            audio_label.setFont(bold_font)
            audio_layout.addWidget(audio_label)
            self.audio_location_input = QLineEdit()
            self.audio_location_input.setReadOnly(True)
            self.audio_location_input.setFixedHeight(28)
            audio_layout.addWidget(self.audio_location_input)
            self.browse_audio_button = QPushButton("Browse... ")
            self.browse_audio_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.browse_audio_button.clicked.connect(self.browse_audio_file)
            audio_layout.addWidget(self.browse_audio_button)
            streaming_layout.addLayout(audio_layout)
            streaming_buttons_layout = QHBoxLayout()
            streaming_buttons_layout.setSpacing(12)
            self.start_streaming_button = QPushButton("Start Streaming")
            self.start_streaming_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.start_streaming_button.clicked.connect(self.start_streaming)
            streaming_buttons_layout.addWidget(self.start_streaming_button)
            self.stop_streaming_button = QPushButton("Stop Streaming")
            self.stop_streaming_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.stop_streaming_button.clicked.connect(self.stop_streaming)
            self.stop_streaming_button.setEnabled(False)
            streaming_buttons_layout.addWidget(self.stop_streaming_button)
            streaming_layout.addLayout(streaming_buttons_layout)
            streaming_group.setLayout(streaming_layout)
            layout.addWidget(streaming_group)
        if role in ["source", "both"]:
            media_control_group = QGroupBox("Media Control (A2DP Sink)")
            media_control_group.setFont(bold_font)
            media_control_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
            media_control_layout = QVBoxLayout()
            media_control_layout.setSpacing(12)
            media_control_layout.setContentsMargins(10, 10, 10, 10)
            # Media control buttons
            control_buttons = QHBoxLayout()
            control_buttons.setSpacing(12)
            self.play_button = QPushButton("Play")
            self.play_button.setFont(bold_font)
            self.play_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.play_button.clicked.connect(lambda: self.media_control("play"))
            control_buttons.addWidget(self.play_button)
            self.pause_button = QPushButton("Pause")
            self.pause_button.setFont(bold_font)
            self.pause_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.pause_button.clicked.connect(lambda: self.media_control("pause"))
            control_buttons.addWidget(self.pause_button)
            self.next_button = QPushButton("Next")
            self.next_button.setFont(bold_font)
            self.next_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.next_button.clicked.connect(lambda: self.media_control("next"))
            control_buttons.addWidget(self.next_button)
            self.previous_button = QPushButton("Previous")
            self.previous_button.setFont(bold_font)
            self.previous_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.previous_button.clicked.connect(lambda: self.media_control("previous"))
            control_buttons.addWidget(self.previous_button)
            self.rewind_button = QPushButton("Rewind")
            self.rewind_button.setFont(bold_font)
            self.rewind_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.rewind_button.clicked.connect(lambda: self.media_control("rewind"))
            control_buttons.addWidget(self.rewind_button)
            self.track_status_label = QLabel("Status: -")
            self.track_status_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
            media_control_layout.addWidget(self.track_status_label)
            self.progress_slider = QSlider(Qt.Orientation.Horizontal)
            self.progress_slider.setRange(0, 100)
            self.progress_slider.setEnabled(False)
            media_control_layout.addWidget(self.progress_slider)
            volume_layout = QHBoxLayout()
            volume_label = QLabel("Volume:")
            volume_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            volume_layout.addWidget(volume_label)
            self.volume_slider = QSlider(Qt.Orientation.Horizontal)
            self.volume_slider.setRange(0, 127)
            self.volume_slider.setFixedWidth(150)
            self.volume_slider.setEnabled(True)
            self.volume_slider.valueChanged.connect(self.set_device_volume)
            volume_layout.addWidget(self.volume_slider)
            media_control_layout.addLayout(volume_layout)
            media_control_layout.addLayout(control_buttons)
            media_control_group.setLayout(media_control_layout)
            layout.addWidget(media_control_group)
            self.sync_volume_slider()
            self.start_playback_polling()
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget
        if role in ["source", "both"]:
            media_control_group = QGroupBox("Media Control (A2DP Sink)")
            media_control_group.setFont(bold_font)
            media_control_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
            media_control_layout = QVBoxLayout()
            media_control_layout.setSpacing(12)
            media_control_layout.setContentsMargins(10, 10, 10, 10)
            control_buttons = QHBoxLayout()
            control_buttons.setSpacing(12)
            self.play_button = QPushButton("Play")
            self.play_button.setFont(bold_font)
            self.play_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.play_button.clicked.connect(lambda: self.media_control("play"))
            control_buttons.addWidget(self.play_button)
            self.pause_button = QPushButton("Pause")
            self.pause_button.setFont(bold_font)
            self.pause_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.pause_button.clicked.connect(lambda: self.media_control("pause"))
            control_buttons.addWidget(self.pause_button)
            self.next_button = QPushButton("Next")
            self.next_button.setFont(bold_font)
            self.next_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.next_button.clicked.connect(lambda: self.media_control("next"))
            control_buttons.addWidget(self.next_button)
            self.previous_button = QPushButton("Previous")
            self.previous_button.setFont(bold_font)
            self.previous_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.previous_button.clicked.connect(lambda: self.media_control("previous"))
            control_buttons.addWidget(self.previous_button)
            self.rewind_button = QPushButton("Rewind")
            self.rewind_button.setFont(bold_font)
            self.rewind_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.rewind_button.clicked.connect(lambda: self.media_control("rewind"))
            control_buttons.addWidget(self.rewind_button)
            media_control_layout.addLayout(control_buttons)
            media_control_group.setLayout(media_control_layout)
            layout.addWidget(media_control_group)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget'''

    '''def build_a2dp_ui(self, device_address):
        """Builds a single A2DP panel combining source streaming and sink media control,based on the device's A2DP roles.

        Args:
            device_address: The Bluetooth address of the device for which the A2DP tab is built.
        Returns:
            A fully configured QWidget containing the A2DP UI components.
        """
        bold_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        a2dp_label = QLabel("<b>A2DP Functionality</b>")
        a2dp_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        a2dp_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(a2dp_label)
        self.device_address_source = device_address
        self.device_address_sink = device_address
        role = self.get_a2dp_role_for_device(device_address)
        if role in ["sink", "both"]:
            streaming_group = QGroupBox("Streaming Audio (A2DP Source)")
            streaming_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
            streaming_layout = QVBoxLayout()
            streaming_layout.setSpacing(10)
            streaming_layout.setContentsMargins(10, 10, 10, 10)
            audio_layout = QHBoxLayout()
            audio_label = QLabel("Audio File: ")
            audio_label.setFont(bold_font)
            audio_layout.addWidget(audio_label)
            self.audio_location_input = QLineEdit()
            self.audio_location_input.setReadOnly(True)
            self.audio_location_input.setFixedHeight(28)
            audio_layout.addWidget(self.audio_location_input)
            self.browse_audio_button = QPushButton("Browse... ")
            self.browse_audio_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.browse_audio_button.clicked.connect(self.browse_audio_file)
            audio_layout.addWidget(self.browse_audio_button)
            streaming_layout.addLayout(audio_layout)
            streaming_buttons_layout = QHBoxLayout()
            streaming_buttons_layout.setSpacing(12)
            self.start_streaming_button = QPushButton("Start Streaming")
            self.start_streaming_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.start_streaming_button.clicked.connect(self.start_streaming)
            streaming_buttons_layout.addWidget(self.start_streaming_button)
            self.stop_streaming_button = QPushButton("Stop Streaming")
            self.stop_streaming_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.stop_streaming_button.clicked.connect(self.stop_streaming)
            self.stop_streaming_button.setEnabled(False)
            streaming_buttons_layout.addWidget(self.stop_streaming_button)
            streaming_layout.addLayout(streaming_buttons_layout)
            streaming_group.setLayout(streaming_layout)
            layout.addWidget(streaming_group)
        if role in ["source", "both"]:
            media_control_group = QGroupBox("Media Control (A2DP Sink)")
            media_control_group.setFont(bold_font)
            media_control_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
            media_control_layout = QVBoxLayout()
            media_control_layout.setSpacing(12)
            media_control_layout.setContentsMargins(10, 10, 10, 10)
            control_buttons = QHBoxLayout()
            control_buttons.setSpacing(12)
            self.play_button = QPushButton("Play")
            self.play_button.setFont(bold_font)
            self.play_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.play_button.clicked.connect(lambda: self.media_control("play"))
            control_buttons.addWidget(self.play_button)
            self.pause_button = QPushButton("Pause")
            self.pause_button.setFont(bold_font)
            self.pause_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.pause_button.clicked.connect(lambda: self.media_control("pause"))
            control_buttons.addWidget(self.pause_button)
            self.next_button = QPushButton("Next")
            self.next_button.setFont(bold_font)
            self.next_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.next_button.clicked.connect(lambda: self.media_control("next"))
            control_buttons.addWidget(self.next_button)
            self.previous_button = QPushButton("Previous")
            self.previous_button.setFont(bold_font)
            self.previous_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.previous_button.clicked.connect(lambda: self.media_control("previous"))
            control_buttons.addWidget(self.previous_button)
            self.rewind_button = QPushButton("Rewind")
            self.rewind_button.setFont(bold_font)
            self.rewind_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.rewind_button.clicked.connect(lambda: self.media_control("rewind"))
            control_buttons.addWidget(self.rewind_button)
            media_control_layout.addLayout(control_buttons)
            media_control_group.setLayout(media_control_layout)
            layout.addWidget(media_control_group)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget'''

    '''def build_gap_ui(self):
        """Build and display the widgets for the GAP profile."""
        bold_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.profile_description_text_browser.setText("<b>GAP Profile Selected</b><br>Use the below methods as required:")
        discoverable_group = QGroupBox("Discoverable Settings")
        discoverable_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
        discoverable_layout = QVBoxLayout()
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("Timeout (s):")
        timeout_label.setFont(bold_font)
        self.discoverable_timeout_input = QLineEdit("0")
        self.discoverable_timeout_input.setPlaceholderText("e.g., 60")
        self.discoverable_timeout_input.setToolTip("Timeout in seconds for discoverable mode")
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(self.discoverable_timeout_input)
        discoverable_layout.addLayout(timeout_layout)
        buttons_layout = QHBoxLayout()
        self.set_discoverable_on_button = QPushButton("Set ON")
        self.set_discoverable_on_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        self.set_discoverable_on_button.clicked.connect(self.set_discoverable_on)
        self.set_discoverable_off_button = QPushButton("Set OFF")
        self.set_discoverable_off_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        self.set_discoverable_off_button.clicked.connect(self.set_discoverable_off)
        self.set_discoverable_off_button.setEnabled(False)
        buttons_layout.addWidget(self.set_discoverable_on_button)
        buttons_layout.addWidget(self.set_discoverable_off_button)
        discoverable_layout.addLayout(buttons_layout)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        self.refresh_button.clicked.connect(self.refresh_discoverable)
        discoverable_layout.addWidget(self.refresh_button)
        discoverable_group.setLayout(discoverable_layout)
        self.profile_methods_layout.addWidget(discoverable_group)
        inquiry_group = QGroupBox("Inquiry")
        inquiry_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
        inquiry_layout = QVBoxLayout()
        inquiry_timeout_layout = QHBoxLayout()
        inquiry_timeout_label = QLabel("Timeout (s):")
        inquiry_timeout_label.setFont(bold_font)
        self.inquiry_timeout_input = QLineEdit("0")
        self.inquiry_timeout_input.setPlaceholderText("e.g., 10")
        self.inquiry_timeout_input.setToolTip("Timeout in seconds for device inquiry")
        inquiry_timeout_layout.addWidget(inquiry_timeout_label)
        inquiry_timeout_layout.addWidget(self.inquiry_timeout_input)
        inquiry_layout.addLayout(inquiry_timeout_layout)
        discovery_buttons_layout = QHBoxLayout()
        self.set_discovery_on_button = QPushButton("Start Inquiry")
        self.set_discovery_on_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        self.set_discovery_on_button.clicked.connect(self.set_discovery_on)
        self.set_discovery_off_button = QPushButton("Stop Inquiry")
        self.set_discovery_off_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        self.set_discovery_off_button.clicked.connect(self.set_discovery_off)
        self.set_discovery_off_button.setEnabled(False)
        discovery_buttons_layout.addWidget(self.set_discovery_on_button)
        discovery_buttons_layout.addWidget(self.set_discovery_off_button)
        inquiry_layout.addLayout(discovery_buttons_layout)
        inquiry_group.setLayout(inquiry_layout)
        self.profile_methods_layout.addWidget(inquiry_group)
        agent_group = QGroupBox("Register Agent")
        agent_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
        agent_layout = QVBoxLayout()
        capability_label = QLabel("Select Capability:")
        capability_label.setFont(bold_font)
        self.capability_combobox = QComboBox()
        self.capability_combobox.setFont(QFont("Arial", 10))
        self.capability_combobox.addItems(["DisplayOnly", "DisplayYesNo", "KeyboardOnly", "NoInputNoOutput", "KeyboardDisplay"])
        self.capability_combobox.setCurrentText("NoInputNoOutput")
        register_agent_button = QPushButton("Register Agent")
        register_agent_button.setFont(bold_font)
        register_agent_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        register_agent_button.clicked.connect(self.register_agent_clicked)
        agent_layout.addWidget(capability_label)
        agent_layout.addWidget(self.capability_combobox)
        agent_layout.addWidget(register_agent_button)
        agent_group.setLayout(agent_layout)
        self.profile_methods_layout.addWidget(agent_group)
        final_refresh_button = QPushButton("Refresh")
        final_refresh_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        final_refresh_button.clicked.connect(self.refresh)
        self.profile_methods_layout.addWidget(final_refresh_button)
        self.profile_methods_layout.addStretch(1)'''

    def build_opp_tab(self, device_address):
        """Builds and returns the OPP (Object Push Profile) panel for Bluetooth file transfer.

        Args:
            device_address: The Bluetooth address of the device for which the OPP tab is built.
        Returns:
            A fully configured QWidget containing the OPP UI components.
        """
        bold_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        opp_label = QLabel("<b>OPP Functionality</b>")
        opp_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        opp_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(opp_label)
        if self.is_connected:
            opp_group = QGroupBox("File Transfer")
            opp_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
            opp_layout = QVBoxLayout()
            opp_layout.setSpacing(10)
            opp_layout.setContentsMargins(10, 10, 10, 10)
            file_selection_layout = QHBoxLayout()
            file_label = QLabel("Select File:")
            file_label.setFont(bold_font)
            file_selection_layout.addWidget(file_label)
            self.opp_location_input = QLineEdit()
            self.opp_location_input.setReadOnly(True)
            self.opp_location_input.setFixedHeight(28)
            file_selection_layout.addWidget(self.opp_location_input)
            self.browse_opp_button = QPushButton("Browse")
            self.browse_opp_button.setFont(bold_font)
            self.browse_opp_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.browse_opp_button.clicked.connect(self.browse_opp_file)
            file_selection_layout.addWidget(self.browse_opp_button)
            opp_layout.addLayout(file_selection_layout)
            button_layout = QHBoxLayout()
            self.send_file_button = QPushButton("Send File")
            self.send_file_button.setFont(bold_font)
            self.send_file_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.send_file_button.clicked.connect(self.send_file)
            button_layout.addWidget(self.send_file_button)
            self.receive_file_button = QPushButton("Receive File")
            self.receive_file_button.setFont(bold_font)
            self.receive_file_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.receive_file_button.clicked.connect(self.receive_file)
            button_layout.addWidget(self.receive_file_button)
            opp_layout.addLayout(button_layout)
            opp_group.setLayout(opp_layout)
            layout.addWidget(opp_group)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        widget.setStyleSheet("background-color:lightblue; color:black; ")
        return widget

    def media_control(self, command):
        """Sends a media control command to the connected Bluetooth device.

        Args:
            command: The media control command to send (e.g., "play", "pause", "next", "previous").
        """
        self.bluetooth_device_manager.media_control(command, address=self.device_address_sink)

    def start_streaming(self):
        """Start A2DP streaming to a selected Bluetooth sink device."""
        audio_path = self.audio_location_input.text().strip()
        if not audio_path or not os.path.exists(audio_path):
            QMessageBox.warning(self, "Invalid Audio File", "Please select a valid audio file to stream.")
            return
        self.log.info("Selected device address for streaming:%s", self.device_address_source)
        if not self.device_address_source:
            QMessageBox.warning(self, "No Device", "Please select a Bluetooth sink device to stream.")
            return
        self.log.info("A2DP streaming started with file:%s", audio_path)
        self.start_streaming_button.setEnabled(False)
        self.stop_streaming_button.setEnabled(True)
        success = self.bluetooth_device_manager.start_a2dp_stream(self.device_address_source, audio_path)
        if not success:
            QMessageBox.critical(self, "Streaming Failed", "Failed to start streaming.")
            self.start_streaming_button.setEnabled(True)
            self.stop_streaming_button.setEnabled(False)

    def stop_streaming(self):
        """Stop active A2DP streaming session."""
        self.log.info("A2DP streaming stopped")
        self.start_streaming_button.setEnabled(True)
        self.stop_streaming_button.setEnabled(False)
        self.bluetooth_device_manager.stop_a2dp_stream()
        if hasattr(self, 'streaming_timer'):
            self.streaming_timer.stop()

    def browse_audio_file(self):
        """Open a file dialog for selecting an audio file."""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(caption="Select Audio File", filter="WAV files (*.wav)")
        if file_path:
            self.audio_location_input.setText(file_path)

    def get_a2dp_role_for_device(self, device_address):
        """Determines the A2DP (Advanced Audio Distribution Profile) role of a Bluetooth device.

        Args:
            device_address: The Bluetooth address of the device to check.
        Returns:
            one from sink/source/both/None
        """
        if not self.bluetooth_device_manager.is_device_connected(device_address):
            return None
        a2dp_sink_devices=self.bluetooth_device_manager.get_connected_a2dp_devices_by_role("sink")
        a2dp_source_devices=self.bluetooth_device_manager.get_connected_a2dp_devices_by_role("source")
        if device_address in a2dp_sink_devices and device_address in a2dp_source_devices:
            return "both"
        elif device_address in a2dp_sink_devices:
            return "sink"
        elif device_address in a2dp_source_devices:
            return "source"
        return None

    def browse_opp_file(self):
        """Open a file dialog to select a file to send via OPP."""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(None, "Select File to Send via OPP", "", "All Files (*)")
        if file_path:
            self.opp_location_input.setText(file_path)

    def send_file(self):
        """Send a selected file to a remote device using OPP."""
        file_path = self.opp_location_input.text()
        if not file_path or not self.device_address:
            QMessageBox.warning(None, "OPP", "Please select a device and a file.")
            return
        self.send_file_button.setEnabled(False)
        self.send_file_button.setText("Sending...")
        try:
            status = self.bluetooth_device_manager.send_file(self.device_address, file_path)
        except Exception as e:
            status = "error"
        self.send_file_button.setEnabled(True)
        self.send_file_button.setText("Send File")
        if status == "complete":
            QMessageBox.information(None, "OPP", "File sent successfully!")
        elif status == "queued":
            QMessageBox.information(None, "OPP", "File transfer is queued. Please wait...")
        elif status == "unknown":
            QMessageBox.warning(None, "OPP", "File transfer status is unknown.")
        else:
            QMessageBox.warning(None, "OPP", "File transfer failed or was rejected.")

    '''def receive_file(self):
        """Start OPP receiver and show user notification after file is received."""
        received_file_path = self.bluetooth_device_manager.receive_file()
        if received_file_path:
            QMessageBox.information(None, "File Received", f"File received successfully:\n{received_file_path}")
        else:
            QMessageBox.warning(None, "OPP", "No file received or receiver failed to start.")'''

    def user_confirm_file_transfer(self,file_path):
        """Prompt user to confirm a file transfer and return their decision."""
        file_name = os.path.basename(file_path)
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Incoming File")
        msg_box.setText(f"Accept incoming file?\n\n{file_name}")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setIcon(QMessageBox.Icon.Question)
        result = msg_box.exec()
        return result == QMessageBox.StandardButton.Yes

    def receive_file(self):
        """Start OPP receiver and handle file transfer."""
        try:
            received_file_path = self.bluetooth_device_manager.receive_file(user_confirm_callback=self.user_confirm_file_transfer)
            if received_file_path:
                QMessageBox.information(None, "File Received", f"File received successfully:\n{received_file_path}")
            else:
                QMessageBox.warning(None, "File Transfer", "No file received or user declined the transfer.")
        except Exception as e:
            QMessageBox.critical(None, "Error", f"An error occurred during file reception:\n{str(e)}")

    def on_profile_tab_changed(self, index):
        """Handles actions to perform when the user switches between profile tabs in the UI.

        Args:
            index: The index of the newly selected tab in the profile tab widget.
        """
        if not hasattr(self, 'device_tab_widget') or index < 0:
            return
        selected_tab = self.device_tab_widget.tabText(index)
        if selected_tab == "A2DP" :
            self.clear_layout(self.a2dp_tab_placeholder)
            layout = QVBoxLayout()
            a2dp_panel = self.build_a2dp_ui(self.device_address)
            self.log.info(self.device_address)
            layout.addWidget(a2dp_panel)
            self.a2dp_tab_placeholder.setLayout(layout)
            self.a2dp_tab_placeholder.update()
        elif selected_tab == "OPP":
            self.clear_layout(self.opp_tab_placeholder)
            layout = QVBoxLayout()
            opp_tab = self.build_opp_tab(self.device_address)
            layout.addWidget(opp_tab)
            self.opp_tab_placeholder.setLayout(layout)
            self.opp_tab_placeholder.update()

    def load_profile_tabs_for_device(self, device_address):
        """Loads and displays profile-related UI tabs for a specific Bluetooth device."""
        bold_font = QFont()
        bold_font.setBold(True)
        is_paired = self.bluetooth_device_manager.is_device_paired(device_address)
        is_connected = self.bluetooth_device_manager.is_device_connected(device_address)
        self.device_address = device_address
        self.profile_description_text_browser.setText("")
        self.profile_description_text_browser.setFont(bold_font)
        if not is_connected:
            self.profile_description_text_browser.setText("Device is not connected. Connect to enable profile controls.")
            warning_label = QLabel("Device is not connected. Connect to enable profile controls.")
            warning_label.setFont(bold_font)
            warning_label.setStyleSheet("color: red; ")
            self.clear_layout(self.profile_methods_layout)
            self.profile_methods_layout.addWidget(warning_label)
            self.add_connection_controls(self.profile_methods_layout, device_address)
            return
        self.profile_description_text_browser.setText(f"Connected Device: {device_address}\nSelect a profile to proceed (A2DP or OPP)")
        self.device_tab_widget = QTabWidget()
        self.device_tab_widget.setMaximumWidth(600)
        self.device_tab_widget.setFont(bold_font)
        self.device_tab_widget.setStyleSheet("color:black; background-color:lightblue; ")
        self.a2dp_tab_placeholder = QWidget()
        self.a2dp_tab_placeholder.setMaximumWidth(600)
        self.opp_tab_placeholder = QWidget()
        self.opp_tab_placeholder.setMaximumWidth(600)
        self.device_tab_widget.addTab(self.a2dp_tab_placeholder, "A2DP")
        self.device_tab_widget.addTab(self.opp_tab_placeholder, "OPP")
        self.device_tab_widget.currentChanged.connect(self.on_profile_tab_changed)
        self.clear_layout(self.profile_methods_layout)
        self.profile_methods_layout.addWidget(self.device_tab_widget)
        self.on_profile_tab_changed(self.device_tab_widget.currentIndex())
        self.add_connection_controls(self.profile_methods_layout, device_address)

    def add_connection_controls(self, layout, device_address):
        """Adds Connect, Disconnect, and Unpair buttons to the provided layout for the specified device.

        Args:
            layout: The layout to which the control buttons will be added.
            device_address: The Bluetooth address of the device the controls apply to.
        """
        bold_font = QFont()
        bold_font.setBold(True)
        button_layout = QHBoxLayout()
        self.is_connected = self.bluetooth_device_manager.is_device_connected(device_address)
        self.is_paired = device_address in self.bluetooth_device_manager.get_paired_devices()
        self.connect_button = QPushButton("Connect")
        self.connect_button.setFont(bold_font)
        self.connect_button.setStyleSheet("color:black; padding:4px; ")
        self.connect_button.setFixedWidth(100)
        self.connect_button.setEnabled(not self.is_connected)
        self.connect_button.clicked.connect(lambda:self.manage_device('connect', device_address, load_profiles=True))
        button_layout.addWidget(self.connect_button)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setFont(bold_font)
        self.disconnect_button.setStyleSheet("color:black; padding:4px; ")
        self.disconnect_button.setFixedWidth(100)
        self.disconnect_button.setEnabled(self.is_connected)
        self.disconnect_button.clicked.connect(lambda:self.manage_device('disconnect', device_address, load_profiles=True))
        button_layout.addWidget(self.disconnect_button)
        self.unpair_button = QPushButton("Unpair")
        self.unpair_button.setFont(bold_font)
        self.unpair_button.setStyleSheet("color:black; padding:4px; ")
        self.unpair_button.setFixedWidth(100)
        self.unpair_button.setEnabled(True)
        self.unpair_button.clicked.connect(lambda:self.manage_device('unpair', device_address, load_profiles=True))
        button_layout.addWidget(self.unpair_button)
        layout.addLayout(button_layout)

    def manage_device(self, action, device_address, load_profiles):
        """Performs a Bluetooth device action and updates the UI.

        Args:
            action: One of 'pair', 'connect', 'disconnect', or 'unpair'.
            device_address: The Bluetooth address of the device.
        """
        if action == 'pair':
            self.log.info("Attempting to pair with %s", device_address)
            if self.bluetooth_device_manager.is_device_paired(device_address):
                QMessageBox.information(self, "Already Paired", f"{device_address} is already paired.")
                self.add_device(device_address)
                return
            success = self.bluetooth_device_manager.pair(device_address)
            if success:
                QMessageBox.information(self, "Pairing Successful", f"{device_address} was paired.")
                self.add_device(device_address)
            else:
                QMessageBox.critical(self, "Pairing Failed", f"Pairing with {device_address} failed.")
        elif action == 'connect':
            success = self.bluetooth_device_manager.connect(device_address)
            if success:
                QMessageBox.information(self, "Connection Successful", f"{device_address} was connected.")
                self.log.info("%s connected successfully", device_address)
                if load_profiles:
                    self.load_profile_tabs_for_device(device_address)
            else:
                QMessageBox.warning(self, "Connection Failed", f"Failed to connect to {device_address}")
        elif action == 'disconnect':
            success = self.bluetooth_device_manager.disconnect(device_address)
            if success:
                QMessageBox.information(self, "Disconnection Successful", f"{device_address} was disconnected.")
                self.log.info("Disconnected from %s", device_address)
            else:
                QMessageBox.warning(self, "Disconnection Failed", f"Could not disconnect from {device_address}")
            self.load_profile_tabs_for_device(device_address)
        elif action == 'unpair':
            success = self.bluetooth_device_manager.remove_device(device_address)
            if success:
                QMessageBox.information(self, "Unpair Successful", f"{device_address} was unpaired.")
                self.log.info("Unpaired %s", device_address)
            else:
                QMessageBox.warning(self, "Unpair Failed", f"Could not unpair {device_address}")
            self.remove_unpaired_device(device_address)
            if self.profiles_list_widget.count() == 1:
                self.profiles_list_widget.itemSelectionChanged.connect(self.profile_selected)
            else:
                self.load_profile_tabs_for_device(device_address)
        else:
            self.log.error("Unknown action:%s", action)

    def remove_unpaired_device(self, unpaired_address):
        """Removes a specific unpaired device from the profiles list (if present)."""
        for i in range(self.profiles_list_widget.count()):
            item_text = self.profiles_list_widget.item(i).text().strip()
            if item_text == unpaired_address:
                self.profiles_list_widget.takeItem(i)
                break

    def register_agent_clicked(self):
        """Function triggered when the 'Register Agent' button is clicked."""
        selected_capability = self.capability_combobox.currentText()
        self.log.info("Registering agent with capability:%s", selected_capability)
        try:
            self.bluetooth_device_manager.register_agent(capability=selected_capability)
            QMessageBox.information(self, "Agent Registered", f"Agent registered with capability : {selected_capability}")
        except Exception as e:
            self.log.info("Failed to register agent:%s", e)
            QMessageBox.critical(self, "Registration Failed", f"Could not register agent.\n{e}")

    def test_application_clicked(self):
        """Create and display the main testing application GUI."""
        self.hcidump_log_name = start_dump_logs(self.interface, self.log, self.log.log_path)
        self.main_grid_layout = QGridLayout()
        bold_font = QFont()
        bold_font.setBold(True)
        # Grid 1: GAP button,Paired_devices, Controller details
        self.gap_button = QPushButton("GAP")
        self.gap_button.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.gap_button.setStyleSheet(styles.gap_button_style_sheet)
        self.gap_button.setFixedWidth(350)
        self.gap_button.setMinimumHeight(30)
        self.gap_button.clicked.connect(lambda: self.profile_selected("GAP "))
        self.main_grid_layout.addWidget(self.gap_button, 0, 0, 1, 2)
        self.profiles_list_widget = QListWidget()
        self.profiles_list_widget.setFont(bold_font)
        self.profiles_list_widget.setContentsMargins(4, 4, 4, 4)
        self.profiles_list_widget.setStyleSheet(styles.profiles_list_style_sheet)
        self.profiles_list_widget.setFixedWidth(350)
        self.profiles_list_widget.itemClicked.connect(lambda item: self.profile_selected(item.text()))
        paired_devices_label = QLabel("Paired Devices")
        paired_devices_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        paired_devices_label.setStyleSheet("color:black; margin-bottom:6px;")
        paired_devices_layout = QVBoxLayout()
        paired_devices_layout.setContentsMargins(8, 8, 8, 8)
        paired_devices_layout.setSpacing(6)
        paired_devices_layout.addWidget(paired_devices_label)
        paired_devices_layout.addWidget(self.profiles_list_widget)
        paired_devices_widget = QWidget()
        paired_devices_widget.setLayout(paired_devices_layout)
        paired_devices_widget.setFixedWidth(350)
        paired_devices_widget.setStyleSheet(styles.panel_style_sheet)
        self.main_grid_layout.addWidget(paired_devices_widget, 1, 0, 4, 2)
        controller_details_widget = QWidget()
        controller_layout = QVBoxLayout(controller_details_widget)
        controller_details_widget.setFixedWidth(350)
        controller_details_widget.setStyleSheet(styles.panel_style_sheet)
        controller_label = QLabel("Controller Details")
        controller_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        controller_label.setStyleSheet("color:black; margin-bottom:8px;")
        controller_layout.addWidget(controller_label)
        details = get_controller_interface_details(self.log, interface=self.interface, detail_level='extended_info')
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(12)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 2)
        self.add_row(0, "Controller Name", details.get("Name", "N/A"))
        self.add_row(1, "Controller Address", details.get("BD_ADDR", "N/A"))
        self.add_row(2, "Link Mode", details.get("Link mode", "N/A"))
        self.add_row(3, "Link Policy", details.get("Link policy", "N/A"))
        self.add_row(4, "HCI Version", details.get("HCI Version", "N/A"))
        self.add_row(5, "LMP Version", details.get("LMP Version", "N/A"))
        self.add_row(6, "Manufacturer", details.get("Manufacturer", "N/A"))
        controller_layout.addLayout(self.grid)
        self.main_grid_layout.addWidget(controller_details_widget, 5, 0, 8, 2)
        # Grid2: Profile description
        profile_description_label = QLabel("Profile Methods or Procedures:")
        profile_description_label.setFont(bold_font)
        profile_description_label.setStyleSheet("color:black;")
        self.main_grid_layout.addWidget(profile_description_label, 0, 2)
        self.profile_description_text_browser = QLabel("Select a profile or device to view methods and procedures.")
        self.profile_description_text_browser.setWordWrap(True)
        self.profile_description_text_browser.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.profile_methods_layout = QVBoxLayout()
        self.profile_methods_widget = QWidget()
        self.profile_methods_widget.setObjectName("ProfileContainer")
        self.profile_methods_widget.setStyleSheet(styles.middle_panel_style_sheet)
        self.profile_methods_widget.setMinimumWidth(350)
        self.profile_methods_widget.setMaximumWidth(500)
        self.profile_methods_widget.setLayout(self.profile_methods_layout)
        self.main_grid_layout.addWidget(self.profile_methods_widget, 1, 2, 12, 2)
        # Grid3: HCI Dump Logs
        dump_logs_label = QLabel("Dump Logs")
        dump_logs_label.setFont(bold_font)
        dump_logs_label.setStyleSheet("color:black;")
        self.main_grid_layout.addWidget(dump_logs_label, 0, 4)
        back_button = QPushButton("Back")
        back_button.setFixedSize(100, 40)
        back_button.setStyleSheet(styles.back_button_style_sheet)
        back_button.clicked.connect(lambda: self.back_callback())
        back_layout = QHBoxLayout()
        back_layout.addWidget(back_button)
        back_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_grid_layout.addLayout(back_layout, 999, 5)
        self.main_grid_layout.setColumnStretch(0, 0)
        self.main_grid_layout.setColumnStretch(1, 0)
        self.main_grid_layout.setColumnStretch(2, 1)
        self.setLayout(self.main_grid_layout)
        self.populate_device_list()

