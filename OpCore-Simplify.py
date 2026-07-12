from Scripts.datasets import os_data
from Scripts.datasets import chipset_data
from Scripts import acpi_guru
from Scripts import compatibility_checker
from Scripts import config_prodigy
from Scripts import gathering_files
from Scripts import hardware_customizer
from Scripts import i18n
from Scripts import kext_maestro
from Scripts import mirror
from Scripts import report_validator
from Scripts import run
from Scripts import smbios
from Scripts import utils
import updater
import os
import sys
import re
import shutil
import traceback
import time

_ = i18n._

class OCPE:
    def __init__(self):
        self.u = utils.Utils("OpCore Simplify")
        self.u.clean_temporary_dir()
        self.ac = acpi_guru.ACPIGuru()
        self.c = compatibility_checker.CompatibilityChecker()
        self.co = config_prodigy.ConfigProdigy()
        self.o = gathering_files.gatheringFiles()
        self.h = hardware_customizer.HardwareCustomizer()
        self.k = kext_maestro.KextMaestro()
        self.s = smbios.SMBIOS()
        self.v = report_validator.ReportValidator()
        self.r = run.Run()
        self.result_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "Results")
        self._mirror_prompted = False

    def select_hardware_report(self):
        self.ac.dsdt = self.ac.acpi.acpi_tables = None

        report_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "SysReport")
        existing_report = os.path.join(report_dir, "Report.json")

        if os.path.exists(existing_report):
            while True:
                self.u.head(_("Hardware Report Found"))
                print("")
                print(_("An existing hardware report was found at:"))
                print("  {}".format(existing_report))
                print("")
                print(_("R. Use existing report (Recommended)"))
                print(_("N. Generate a new report"))
                print(_("C. Cancel"))
                print("")
                choice = self.u.request_input(_("Select an option (R/n/C): ")).strip().lower()
                if choice == "r" or choice == "":
                    self.u.head(_("Select hardware report"))
                    print("")
                    print(_("Using existing hardware report..."))
                    report_data = self.u.read_file(existing_report)
                    if report_data:
                        acpitables_dir = os.path.join(report_dir, "ACPI")
                        self.ac.read_acpi_tables(acpitables_dir)
                        return existing_report, report_data
                    print("")
                    print(_("Could not read the existing report."))
                    print("")
                    self.u.request_input(_("Press Enter to continue..."))
                    break
                elif choice == "n":
                    print("")
                    print(_("Generating a new report..."))
                    break
                elif choice == "c":
                    self.u.exit_program()

        while True:
            self.u.head(_("Select hardware report"))
            print("")
            is_mac = sys.platform == "darwin"
            is_win = os.name == "nt"
            if is_win:
                print("\033[1;93m" + _("Note:") + "\033[0m")
                print(_("- Ensure you are using the latest version of Hardware Sniffer before generating the hardware report."))
                print(_("- Hardware Sniffer will not collect information related to Resizable BAR option of GPU (disabled by default) and monitor connections in Windows PE."))
                print("")
            if is_win or is_mac:
                print(_("E. Export hardware report (Recommended)"))
                print("")
            print(_("Q. Quit"))
            print("")
        
            user_input = self.u.request_input(_("Drag and drop your hardware report here (.JSON){}: ").format(_(" or type \"E\" to export") if (is_win or is_mac) else ""))
            if user_input.lower() == "q":
                self.u.exit_program()
            if user_input.lower() == "e":
                hardware_sniffer = self.o.gather_hardware_sniffer()

                if not hardware_sniffer:
                    continue

                self.u.head(_("Exporting Hardware Report"))
                print("")
                print(_("Exporting hardware report to {}...").format(report_dir))
                
                output = self.r.run({
                    "args":[hardware_sniffer, "-e", "-o", report_dir]
                })

                if output[-1] != 0:
                    error_code = output[-1]
                    if error_code == 3:
                        error_message = _("Error collecting hardware.")
                    elif error_code == 4:
                        error_message = _("Error generating hardware report.")
                    elif error_code == 5:
                        error_message = _("Error dumping ACPI tables.")
                    else:
                        error_message = _("Unknown error.")

                    print("")
                    print(_("Could not export the hardware report. {}").format(error_message))
                    print(_("Please try again or using Hardware Sniffer manually."))
                    print("")
                    self.u.request_input()
                    continue
                else:
                    report_path = os.path.join(report_dir, "Report.json")
                    acpitables_dir = os.path.join(report_dir, "ACPI")

                    report_data = self.u.read_file(report_path)
                    self.ac.read_acpi_tables(acpitables_dir)
                    
                    return report_path, report_data
                
            path = self.u.normalize_path(user_input)
            
            is_valid, errors, warnings, data = self.v.validate_report(path)
            
            self.v.show_validation_report(path, is_valid, errors, warnings)
            if not is_valid or errors:
                print("")
                print("\033[32m" + _("Suggestion: Please re-export the hardware report and try again.") + "\033[0m")
                print("")
                self.u.request_input(_("Press Enter to go back..."))
            else:
                return path, data
            
    def show_oclp_warning(self):
        while True:
            self.u.head(_("OpenCore Legacy Patcher Warning"))
            print("")
            print(_("1. OpenCore Legacy Patcher is the only solution to enable dropped GPU and Broadcom WiFi"))
            print(_("   support in newer macOS versions, as well as to bring back AppleHDA for macOS Tahoe 26."))
            print("")
            print(_("2. OpenCore Legacy Patcher disables macOS security features including SIP and AMFI, which may"))
            print(_("   lead to issues such as requiring full installers for updates, application crashes, and"))
            print(_("   system instability."))
            print("")
            print(_("3. OpenCore Legacy Patcher is not officially supported for Hackintosh community."))
            print("")
            print("\033[1;91m" + _("Important:") + "\033[0m")
            print(_("Please consider these risks carefully before proceeding."))
            print("")
            print("\033[1;96m" + _("Support for macOS Tahoe 26:") + "\033[0m")
            print(_("To patch macOS Tahoe 26, you must download OpenCore-Patcher 3.0.0 or newer from"))
            print(_("my repository: \033[4mlzhoang2801/OpenCore-Legacy-Patcher\033[0m on GitHub."))
            print(_("Older or official Dortania releases are NOT supported for Tahoe 26."))
            print("")
            option = self.u.request_input(_("Do you want to continue with OpenCore Legacy Patcher? (yes/No): ")).strip().lower()
            if option == "yes":
                return True
            elif option == "no":
                return False

    def select_macos_version(self, hardware_report, native_macos_version, ocl_patched_macos_version):
        suggested_macos_version = native_macos_version[1]
        version_pattern = re.compile(r'^(\d+)(?:\.(\d+)(?:\.(\d+))?)?$')

        for device_type in ("GPU", "Network", "Bluetooth", "SD Controller"):
            if device_type in hardware_report:
                for device_name, device_props in hardware_report[device_type].items():
                    if device_props.get("Compatibility", (None, None)) != (None, None):
                        if device_type == "GPU" and device_props.get("Device Type") == "Integrated GPU":
                            device_id = device_props.get("Device ID", "")[5:]

                            if device_props.get("Manufacturer") == "AMD" or device_id.startswith(("59", "87C0")):
                                suggested_macos_version = "22.99.99"
                            elif device_id.startswith(("09", "19")):
                                suggested_macos_version = "21.99.99"

                        if self.u.parse_darwin_version(suggested_macos_version) > self.u.parse_darwin_version(device_props.get("Compatibility")[0]):
                            suggested_macos_version = device_props.get("Compatibility")[0]

        while True:
            if "Beta" in os_data.get_macos_name_by_darwin(suggested_macos_version):
                suggested_macos_version = "{}{}".format(int(suggested_macos_version[:2]) - 1, suggested_macos_version[2:])
            else:
                break

        while True:
            self.u.head(_("Select macOS Version"))
            if native_macos_version[1][:2] != suggested_macos_version[:2]:
                print("")
                print("\033[1;36m" + _("Suggested macOS version:") + "\033[0m")
                print(_("- For better compatibility and stability, we suggest you to use only {} or older.").format(os_data.get_macos_name_by_darwin(suggested_macos_version)))
            print("")
            print(_("Available macOS versions:"))
            print("")

            oclp_min = int(ocl_patched_macos_version[-1][:2]) if ocl_patched_macos_version else 99
            oclp_max = int(ocl_patched_macos_version[0][:2]) if ocl_patched_macos_version else 0
            min_version = min(int(native_macos_version[0][:2]), oclp_min)
            max_version = max(int(native_macos_version[-1][:2]), oclp_max)

            for darwin_version in range(min_version, max_version + 1):
                name = os_data.get_macos_name_by_darwin(str(darwin_version))
                label = " (\033[1;93m" + _("Requires OpenCore Legacy Patcher") + "\033[0m)" if oclp_min <= darwin_version <= oclp_max else ""
                print("   {}. {}{}".format(darwin_version, name, label))

            print("")
            print("\033[1;93m" + _("Note:") + "\033[0m")
            print(_("- To select a major version, enter the number (e.g., 19)."))
            print(_("- To specify a full version, use the Darwin version format (e.g., 22.4.6)."))
            print("")
            print(_("Q. Quit"))
            print("")
            option = self.u.request_input(_("Please enter the macOS version you want to use (default: {}): ").format(os_data.get_macos_name_by_darwin(suggested_macos_version))) or suggested_macos_version
            if option.lower() == "q":
                self.u.exit_program()

            match = version_pattern.match(option)
            if match:
                target_version = "{}.{}.{}".format(match.group(1), match.group(2) if match.group(2) else 99, match.group(3) if match.group(3) else 99)
                
                if ocl_patched_macos_version and self.u.parse_darwin_version(ocl_patched_macos_version[-1]) <= self.u.parse_darwin_version(target_version) <= self.u.parse_darwin_version(ocl_patched_macos_version[0]):
                    return target_version
                elif self.u.parse_darwin_version(native_macos_version[0]) <= self.u.parse_darwin_version(target_version) <= self.u.parse_darwin_version(native_macos_version[-1]):
                    return target_version

    def build_opencore_efi(self, hardware_report, disabled_devices, smbios_model, macos_version, needs_oclp):
        steps = [
            _("Copying EFI base to results folder"),
            _("Applying ACPI patches"),
            _("Copying kexts and snapshotting to config.plist"),
            _("Generating config.plist"),
            _("Cleaning up unused drivers, resources, and tools")
        ]
        
        title = _("Building OpenCore EFI")

        self.u.progress_bar(title, steps, 0)
        self.u.create_folder(self.result_dir, remove_content=True)

        if not os.path.exists(self.k.ock_files_dir):
            raise Exception("Directory '{}' does not exist.".format(self.k.ock_files_dir))
        
        source_efi_dir = os.path.join(self.k.ock_files_dir, "OpenCorePkg")
        shutil.copytree(source_efi_dir, self.result_dir, dirs_exist_ok=True)

        config_file = os.path.join(self.result_dir, "EFI", "OC", "config.plist")
        config_data = self.u.read_file(config_file)
        
        if not config_data:
            raise Exception("Error: The file {} does not exist.".format(config_file))
        
        self.u.progress_bar(title, steps, 1)
        config_data["ACPI"]["Add"] = []
        config_data["ACPI"]["Delete"] = []
        config_data["ACPI"]["Patch"] = []
        if self.ac.ensure_dsdt():
            self.ac.hardware_report = hardware_report
            self.ac.disabled_devices = disabled_devices
            self.ac.acpi_directory = os.path.join(self.result_dir, "EFI", "OC", "ACPI")
            self.ac.smbios_model = smbios_model
            self.ac.lpc_bus_device = self.ac.get_lpc_name()

            for patch in self.ac.patches:
                if patch.checked:
                    if patch.name == "BATP":
                        patch.checked = getattr(self.ac, patch.function_name)()
                        self.k.kexts[kext_maestro.kext_data.kext_index_by_name.get("ECEnabler")].checked = patch.checked
                        continue

                    acpi_load = getattr(self.ac, patch.function_name)()

                    if not isinstance(acpi_load, dict):
                        continue

                    config_data["ACPI"]["Add"].extend(acpi_load.get("Add", []))
                    config_data["ACPI"]["Delete"].extend(acpi_load.get("Delete", []))
                    config_data["ACPI"]["Patch"].extend(acpi_load.get("Patch", []))
        
        config_data["ACPI"]["Patch"].extend(self.ac.dsdt_patches)
        config_data["ACPI"]["Patch"] = self.ac.apply_acpi_patches(config_data["ACPI"]["Patch"])

        self.u.progress_bar(title, steps, 2)
        kexts_directory = os.path.join(self.result_dir, "EFI", "OC", "Kexts")
        self.k.install_kexts_to_efi(macos_version, kexts_directory)
        config_data["Kernel"]["Add"] = self.k.load_kexts(hardware_report, macos_version, kexts_directory)

        self.u.progress_bar(title, steps, 3)
        self.co.genarate(hardware_report, disabled_devices, smbios_model, macos_version, needs_oclp, self.k.kexts, config_data)
        self.u.write_file(config_file, config_data)

        self.u.progress_bar(title, steps, 4)
        files_to_remove = []

        drivers_directory = os.path.join(self.result_dir, "EFI", "OC", "Drivers")
        driver_list = self.u.find_matching_paths(drivers_directory, extension_filter=".efi")
        driver_loaded = [kext.get("Path") for kext in config_data.get("UEFI").get("Drivers")]
        for driver_path, _ in driver_list:
            if not driver_path in driver_loaded:
                files_to_remove.append(os.path.join(drivers_directory, driver_path))

        resources_audio_dir = os.path.join(self.result_dir, "EFI", "OC", "Resources", "Audio")
        if os.path.exists(resources_audio_dir):
            files_to_remove.append(resources_audio_dir)

        picker_variant = config_data.get("Misc", {}).get("Boot", {}).get("PickerVariant")
        if picker_variant in (None, "Auto"):
            picker_variant = "Acidanthera/GoldenGate" 
        if os.name == "nt":
            picker_variant = picker_variant.replace("/", "\\")

        resources_image_dir = os.path.join(self.result_dir, "EFI", "OC", "Resources", "Image")
        available_picker_variants = self.u.find_matching_paths(resources_image_dir, type_filter="dir")

        for variant_name, variant_type in available_picker_variants:
            variant_path = os.path.join(resources_image_dir, variant_name)
            if ".icns" in ", ".join(os.listdir(variant_path)):
                if picker_variant not in variant_name:
                    files_to_remove.append(variant_path)

        tools_directory = os.path.join(self.result_dir, "EFI", "OC", "Tools")
        tool_list = self.u.find_matching_paths(tools_directory, extension_filter=".efi")
        tool_loaded = [tool.get("Path") for tool in config_data.get("Misc").get("Tools")]
        for tool_path, _ in tool_list:
            if not tool_path in tool_loaded:
                files_to_remove.append(os.path.join(tools_directory, tool_path))

        if "manifest.json" in os.listdir(self.result_dir):
            files_to_remove.append(os.path.join(self.result_dir, "manifest.json"))

        for file_path in files_to_remove:
            try:
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
            except Exception as e:
                print("Failed to remove file: {}".format(e))
        
        self.u.progress_bar(title, steps, len(steps), done=True)
        
        print(_("OpenCore EFI build complete."))
        time.sleep(2)
        
    def check_bios_requirements(self, org_hardware_report, hardware_report):
        requirements = []
        
        org_firmware_type = org_hardware_report.get("BIOS", {}).get("Firmware Type", "Unknown")
        firmware_type = hardware_report.get("BIOS", {}).get("Firmware Type", "Unknown")
        if org_firmware_type == "Legacy" and firmware_type == "UEFI":
            requirements.append("Enable UEFI mode (disable Legacy/CSM (Compatibility Support Module))")

        secure_boot = hardware_report.get("BIOS", {}).get("Secure Boot", "Unknown")
        if secure_boot != "Disabled":
            requirements.append("Disable Secure Boot")
        
        if hardware_report.get("Motherboard", {}).get("Platform") == "Desktop" and hardware_report.get("Motherboard", {}).get("Chipset") in chipset_data.IntelChipsets[112:]:
            resizable_bar_enabled = any(gpu_props.get("Resizable BAR", "Disabled") == "Enabled" for gpu_props in hardware_report.get("GPU", {}).values())
            if not resizable_bar_enabled:
                requirements.append("Enable Above 4G Decoding")
                requirements.append("Disable Resizable BAR/Smart Access Memory")
                
        return requirements

    def before_using_efi(self, org_hardware_report, hardware_report):
        self.u.head(_("Before Using EFI"))
        print("")                 
        print("\033[93m" + _("Please complete the following steps:") + "\033[0m")
        print("")
        
        bios_requirements = self.check_bios_requirements(org_hardware_report, hardware_report)
        if bios_requirements:
            print(_("* BIOS/UEFI Settings Required:"))
            for requirement in bios_requirements:
                print("    - {}".format(requirement))
            print("")
        
        print(_("* USB Mapping:"))
        print(_("    - Use USBToolBox tool to map USB ports."))
        efi_path = "EFI\\OC\\Kexts" if os.name == "nt" else "EFI/OC/Kexts"
        print(_("    - Add created UTBMap.kext into the {} folder.").format(efi_path))
        print(_("    - Remove UTBDefault.kext in the {} folder.").format(efi_path))
        print(_("    - Edit config.plist:"))
        print(_("        - Use ProperTree to open your config.plist."))
        print(_("        - Run OC Snapshot by pressing Command/Ctrl + R."))
        print(_("        - If you have more than 15 ports on a single controller, enable the XhciPortLimit patch."))
        print(_("        - Save the file when finished."))
        print("")
        self.u.request_input()
        self.u.open_folder(self.result_dir)

    def main(self):
        if not self._mirror_prompted:
            self._mirror_prompted = True
            if mirror.get_mirror_name() == "None":
                self.u.head(_("Download Mirror"))
                print("")
                print("  " + _("Would you like to use a download mirror?"))
                print("  " + _("Mirrors can accelerate GitHub downloads in some regions."))
                print("")
                choice = self.u.request_input(_("Select mirror? (y/N): ")).strip().lower()
                if choice == "y":
                    self.u.select_mirror()

        hardware_report_path = None
        native_macos_version = None
        disabled_devices = None
        macos_version = None
        ocl_patched_macos_version = None
        needs_oclp = False
        smbios_model = None

        while True:
            self.u.head()
            print("")
            print("  " + _("Hardware Report: {}").format(hardware_report_path or _('Not selected')))
            if hardware_report_path:
                print("")
                macos_label = _("macOS Version:   {}").format(os_data.get_macos_name_by_darwin(macos_version) if macos_version else _('Not selected'))
                if macos_version:
                    macos_label += ' (' + macos_version + ')'
                if needs_oclp:
                    macos_label += '. \033[1;93m' + _('Requires OpenCore Legacy Patcher') + '\033[0m'
                print("  " + macos_label)
                print("  " + _("SMBIOS:          {}").format(smbios_model or _('Not selected')))
                if disabled_devices:
                    print("  " + _("Disabled Devices:"))
                    for device, __ in disabled_devices.items():
                        print("    - {}".format(device))
            print("")

            print(_("1. Select Hardware Report"))
            print(_("2. Select macOS Version"))
            print(_("3. Customize ACPI Patch"))
            print(_("4. Customize Kexts"))
            print(_("5. Customize SMBIOS Model"))
            print(_("6. Build OpenCore EFI"))
            print(_("7. Language"))
            print(_("8. Download Mirror"))
            print("")
            print(_("Q. Quit"))
            print("")

            option = self.u.request_input(_("Select an option: "))
            if option.lower() == "q":
                self.u.exit_program()
           
            if option == "1":
                hardware_report_path, hardware_report = self.select_hardware_report()
                hardware_report, native_macos_version, ocl_patched_macos_version = self.c.check_compatibility(hardware_report)
                macos_version = self.select_macos_version(hardware_report, native_macos_version, ocl_patched_macos_version)
                customized_hardware, disabled_devices, needs_oclp = self.h.hardware_customization(hardware_report, macos_version)
                smbios_model = self.s.select_smbios_model(customized_hardware, macos_version)
                if not self.ac.ensure_dsdt():
                    self.ac.select_acpi_tables()
                self.ac.select_acpi_patches(customized_hardware, disabled_devices)
                needs_oclp = self.k.select_required_kexts(customized_hardware, macos_version, needs_oclp, self.ac.patches)
                self.s.smbios_specific_options(customized_hardware, smbios_model, macos_version, self.ac.patches, self.k)

            if not hardware_report_path:
                self.u.head()
                print("\n\n")
                print("\033[1;93m" + _("Please select a hardware report first.") + "\033[0m")
                print("\n\n")
                self.u.request_input(_("Press Enter to go back..."))
                continue

            if option == "2":
                macos_version = self.select_macos_version(hardware_report, native_macos_version, ocl_patched_macos_version)
                customized_hardware, disabled_devices, needs_oclp = self.h.hardware_customization(hardware_report, macos_version)
                smbios_model = self.s.select_smbios_model(customized_hardware, macos_version)
                needs_oclp = self.k.select_required_kexts(customized_hardware, macos_version, needs_oclp, self.ac.patches)
                self.s.smbios_specific_options(customized_hardware, smbios_model, macos_version, self.ac.patches, self.k)
            elif option == "3":
                self.ac.customize_patch_selection()
            elif option == "4":
                self.k.kext_configuration_menu(macos_version)
            elif option == "5":
                smbios_model = self.s.customize_smbios_model(customized_hardware, smbios_model, macos_version)
                self.s.smbios_specific_options(customized_hardware, smbios_model, macos_version, self.ac.patches, self.k)
            elif option == "7":
                self.u.select_language()
            elif option == "8":
                self.u.select_mirror()
            elif option == "6":
                if needs_oclp and not self.show_oclp_warning():
                    macos_version = self.select_macos_version(hardware_report, native_macos_version, ocl_patched_macos_version)
                    customized_hardware, disabled_devices, needs_oclp = self.h.hardware_customization(hardware_report, macos_version)
                    smbios_model = self.s.select_smbios_model(customized_hardware, macos_version)
                    needs_oclp = self.k.select_required_kexts(customized_hardware, macos_version, needs_oclp, self.ac.patches)
                    self.s.smbios_specific_options(customized_hardware, smbios_model, macos_version, self.ac.patches, self.k)
                    continue

                try:
                    self.o.gather_bootloader_kexts(self.k.kexts, macos_version)
                except Exception as e:
                    print("\033[91m" + _("Error: {}").format(e) + "\033[0m")
                    print("")
                    self.u.request_input(_("Press Enter to continue..."))
                    continue
                
                self.build_opencore_efi(customized_hardware, disabled_devices, smbios_model, macos_version, needs_oclp)
                self.before_using_efi(hardware_report, customized_hardware)

                self.u.head(_("Result"))
                print("")
                print(_("Your OpenCore EFI for {} has been built at:").format(customized_hardware.get("Motherboard").get("Name")))
                print("\t{}".format(self.result_dir))
                print("")
                self.u.request_input(_("Press Enter to main menu..."))

if __name__ == '__main__':
    update_flag = updater.Updater().run_update()
    if update_flag:
        os.execv(sys.executable, ['python3'] + sys.argv)

    o = OCPE()
    while True:
        try:
            o.main()
        except Exception as e:
            o.u.head("An Error Occurred")
            print("")
            print(traceback.format_exc())
            o.u.request_input()