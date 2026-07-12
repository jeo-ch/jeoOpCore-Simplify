from Scripts import github
from Scripts import kext_maestro
from Scripts import integrity_checker
from Scripts import resource_fetcher
from Scripts import utils
from Scripts.i18n import _
import os
import re
import shutil
import subprocess
import platform

os_name = platform.system()

class gatheringFiles:
    def __init__(self):
        self.utils = utils.Utils()
        self.github = github.Github()
        self.kext = kext_maestro.KextMaestro()
        self.fetcher = resource_fetcher.ResourceFetcher()
        self.integrity_checker = integrity_checker.IntegrityChecker()
        self.dortania_builds_url = "https://raw.githubusercontent.com/dortania/build-repo/builds/latest.json"
        self.ocbinarydata_url = "https://github.com/acidanthera/OcBinaryData/archive/refs/heads/master.zip"
        self.amd_vanilla_patches_url = "https://raw.githubusercontent.com/laobamac/AMD_Vanilla/refs/heads/master/patches.plist"
        self.aquantia_macos_patches_url = "https://raw.githubusercontent.com/CaseySJ/Aquantia-macOS-Patches/refs/heads/main/CaseySJ-Aquantia-Patch-Sets-1-and-2.plist"
        self.hyper_threading_patches_url = "https://github.com/b00t0x/CpuTopologyRebuild/raw/refs/heads/master/patches_ht.plist"
        self.temporary_dir = self.utils.get_temporary_dir()
        self.ock_files_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "OCK_Files")
        self.download_history_file = os.path.join(self.ock_files_dir, "history.json")

    def _load_download_history(self):
        history_data = self.utils.read_file(self.download_history_file)
        return {item["product_name"]: item for item in history_data if item.get("product_name")} if isinstance(history_data, list) else {}
    
    def _save_download_history(self, local_download_history, product_name, product_id, product_url, sha256_hash):
        local_download_history[product_name] = {
            "product_name": product_name, 
            "id": product_id,
            "url": product_url,
            "sha256": sha256_hash
        }
        
        self.utils.create_folder(os.path.dirname(self.download_history_file))
        sorted_history = sorted(local_download_history.values(), key=lambda x: x.get("product_name", ""))
        self.utils.write_file(self.download_history_file, sorted_history)

    def fetch_latest_products_info(self, kexts, local_download_history):
        latest_products = {k: v.copy() for k, v in local_download_history.items()}
        dortania_builds_data = self.fetcher.fetch_and_parse_content(self.dortania_builds_url, "json")
        if dortania_builds_data is not None and not isinstance(dortania_builds_data, dict):
            dortania_builds_data = None
        seen_repos = set()

        def add_product_info(products):
            if isinstance(products, dict):
                products = [products]

            for product in products:
                name = product.get("product_name")
                if not product or not name:
                    continue

                if name not in latest_products:
                    latest_products[name] = product
                else:
                    latest_products[name].update(product)

        def get_from_dortania(name):
            if dortania_builds_data is None:
                return None
            entry = dortania_builds_data.get(name)
            if not entry:
                return None
            versions = entry.get("versions")
            if not versions:
                return None
            release = versions[0].get("release", {})
            links = versions[0].get("links", {})
            hashes = versions[0].get("hashes", {}).get("release", {})
            return {
                "product_name": name,
                "id": release.get("id"),
                "url": links.get("release"),
                "sha256": hashes.get("sha256")
            }

        for kext in kexts:
            if not kext.checked:
                continue

            if kext.download_info:
                if not kext.download_info.get("sha256"):
                    kext.download_info["sha256"] = None
                add_product_info({"product_name": kext.name, **kext.download_info})
            elif kext.github_repo and kext.github_repo.get("repo") not in seen_repos:
                name = kext.github_repo.get("repo")
                seen_repos.add(name)
                product_info = get_from_dortania(name)
                if product_info:
                    add_product_info(product_info)
                else:
                    latest_release = self.github.get_latest_release(kext.github_repo.get("owner"), kext.github_repo.get("repo")) or {}
                    add_product_info(latest_release.get("assets"))

        opencore_info = get_from_dortania("OpenCorePkg")
        if opencore_info:
            add_product_info(opencore_info)

        return latest_products
    
    def move_bootloader_kexts_to_product_directory(self, product_name):
        if not os.path.exists(self.temporary_dir):
            raise FileNotFoundError(_("The directory {} does not exist.").format(self.temporary_dir))
        
        temp_product_dir = os.path.join(self.temporary_dir, product_name)
        
        if not "OpenCore" in product_name:
            kext_paths = self.utils.find_matching_paths(temp_product_dir, extension_filter=".kext")
            for kext_path, _ in kext_paths:
                source_kext_path = os.path.join(self.temporary_dir, product_name, kext_path)
                destination_kext_path = os.path.join(self.ock_files_dir, product_name, os.path.basename(kext_path))
                
                if "research" in kext_path.lower() or "debug" in kext_path.lower() or "Contents" in kext_path or not self.kext.process_kext(temp_product_dir, kext_path):
                    continue
                
                shutil.move(source_kext_path, destination_kext_path)
        else:
            source_bootloader_path = os.path.join(self.temporary_dir, product_name, "X64", "EFI")
            if os.path.exists(source_bootloader_path):
                destination_efi_path = os.path.join(self.ock_files_dir, product_name, os.path.basename(source_bootloader_path))
                shutil.move(source_bootloader_path, destination_efi_path)
                source_config_path = os.path.join(os.path.dirname(os.path.dirname(source_bootloader_path)), "Docs", "Sample.plist")
                destination_config_path = os.path.join(destination_efi_path, "OC", "config.plist")
                shutil.move(source_config_path, destination_config_path)

            ocbinarydata_dir = os.path.join(self.temporary_dir, "OcBinaryData", "OcBinaryData-master")
            if os.path.exists(ocbinarydata_dir):
                background_picker_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "datasets", "background_picker.icns")
                product_dir = os.path.join(self.ock_files_dir, product_name)
                efi_dirs = self.utils.find_matching_paths(product_dir, name_filter="EFI", type_filter="dir")

                for efi_dir, __ in efi_dirs:
                    for dir_name in os.listdir(ocbinarydata_dir):
                        source_dir = os.path.join(ocbinarydata_dir, dir_name)
                        destination_dir = os.path.join(destination_efi_path, "OC", dir_name)
                        if os.path.isdir(destination_dir):
                            shutil.copytree(source_dir, destination_dir, dirs_exist_ok=True)

                    resources_image_dir = os.path.join(product_dir, efi_dir, "OC", "Resources", "Image")
                    picker_variants = self.utils.find_matching_paths(resources_image_dir, type_filter="dir")
                    for picker_variant, __ in picker_variants:
                        if ".icns" in ", ".join(os.listdir(os.path.join(resources_image_dir, picker_variant))):
                            shutil.copy(background_picker_path, os.path.join(resources_image_dir, picker_variant, "Background.icns"))

            macserial_paths = self.utils.find_matching_paths(temp_product_dir, name_filter="macserial", type_filter="file")
            if macserial_paths:
                for macserial_path, __ in macserial_paths:
                    source_macserial_path = os.path.join(self.temporary_dir, product_name, macserial_path)
                    destination_macserial_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), os.path.basename(macserial_path))
                    shutil.move(source_macserial_path, destination_macserial_path)
                    if os.name != "nt":
                        subprocess.run(["chmod", "+x", destination_macserial_path])
        
        return True
    
    def _check_local_product_valid(self, product_name, local_download_history):
        history_item = local_download_history.get(product_name)
        if history_item is None:
            return False
        asset_dir = os.path.join(self.ock_files_dir, product_name)
        manifest_path = os.path.join(asset_dir, "manifest.json")
        folder_is_valid, _ = self.integrity_checker.verify_folder_integrity(asset_dir, manifest_path)
        return folder_is_valid

    def _resolve_product_name(self, product, kexts, macos_version):
        product_name = product.name if not isinstance(product, dict) else product.get("Name")

        if product_name == "AirportItlwm":
            version = macos_version[:2]
            if all((self.utils.parse_darwin_version("24.0.0") <= self.utils.parse_darwin_version(macos_version),
                    kexts[kext_maestro.kext_data.kext_index_by_name.get("IOSkywalkFamily")].checked,
                    kexts[kext_maestro.kext_data.kext_index_by_name.get("IO80211FamilyLegacy")].checked)):
                version = "22"
            elif self.utils.parse_darwin_version("23.4.0") <= self.utils.parse_darwin_version(macos_version):
                version = "23.4"
            elif self.utils.parse_darwin_version("23.0.0") <= self.utils.parse_darwin_version(macos_version):
                version = "23.0"
            product_name += version
        elif "VoodooPS2" in product_name:
            product_name = "VoodooPS2"
        elif product_name == "BlueToolFixup" or product_name.startswith("Brcm"):
            product_name = "BrcmPatchRAM"
        elif product_name.startswith("Ath3kBT"):
            product_name = "Ath3kBT"
        elif product_name.startswith("IntelB"):
            product_name = "IntelBluetoothFirmware"
        elif product_name.startswith("VoodooI2C"):
            product_name = "VoodooI2C"
        elif product_name == "UTBDefault":
            product_name = "USBToolBox"

        return product_name

    def gather_bootloader_kexts(self, kexts, macos_version):
        self.utils.head(_("Gathering Files"))
        print("")
        print(_("Checking local files..."))
        local_download_history = self._load_download_history()

        pending_products = set()
        for product in kexts + [{"Name": "OpenCorePkg"}]:
            if not isinstance(product, dict) and not product.checked:
                continue
            product_name = self._resolve_product_name(product, kexts, macos_version)
            if not self._check_local_product_valid(product_name, local_download_history):
                pending_products.add(product_name)

        if not pending_products:
            print(_("All files are up to date."))
            return True

        print(_("Please wait for download OpenCorePkg, kexts and macserial..."))

        latest_products = self.fetch_latest_products_info(kexts, local_download_history)
        
        self.utils.create_folder(self.temporary_dir)

        seen_download_urls = set()

        for product in kexts + [{"Name": "OpenCorePkg"}]:
            if not isinstance(product, dict) and not product.checked:
                continue

            product_name = self._resolve_product_name(product, kexts, macos_version)

            product_info = latest_products.get(product_name)
            if product_info is None:
                if hasattr(product, 'github_repo') and product.github_repo:
                    product_info = latest_products.get(product.github_repo.get("repo"))
            
            if product_info is None:
                print("\n")
                print(_("Could not find download URL for {}.").format(product_name))
                continue

            product_id = product_info.get("id")
            product_download_url = product_info.get("url")
            sha256_hash = product_info.get("sha256")

            if product_download_url in seen_download_urls:
                continue
            seen_download_urls.add(product_download_url)

            history_item = local_download_history.get(product_name)
            asset_dir = os.path.join(self.ock_files_dir, product_name)
            manifest_path = os.path.join(asset_dir, "manifest.json")

            if history_item is not None:
                is_latest_id = (product_id == history_item.get("id"))
                folder_is_valid, _issues = self.integrity_checker.verify_folder_integrity(asset_dir, manifest_path)
                
                if is_latest_id and folder_is_valid:
                    print(f"\n{_('Latest version of {} already downloaded.').format(product_name)}")
                    continue

            print("")
            print(_("Updating") if history_item is not None else _("Please wait for download"), end=" ")
            print(_("{}...").format(product_name))
            if product_download_url:
                print(_("from {}").format(product_download_url))
                print("")
            else:
                print("")
                print(_("Could not find download URL for {}.").format(product_name))
                print("")
                self.utils.request_input()
                shutil.rmtree(self.temporary_dir, ignore_errors=True)
                return False

            zip_path = os.path.join(self.temporary_dir, product_name) + ".zip"
            if not self.fetcher.download_and_save_file(product_download_url, zip_path, sha256_hash):
                folder_is_valid, _issues = self.integrity_checker.verify_folder_integrity(asset_dir, manifest_path)
                if history_item is not None and folder_is_valid:
                    print(_("Using previously downloaded version of {}.").format(product_name))
                    continue
                else:
                    raise Exception(_("Could not download {} at this time. Please try again later.").format(product_name))
            
            self.utils.extract_zip_file(zip_path)
            self.utils.create_folder(asset_dir, remove_content=True)
            
            dirs_to_scan = [os.path.join(self.temporary_dir, product_name)]
            while dirs_to_scan:
                current_dir = dirs_to_scan.pop()
                if not os.path.isdir(current_dir):
                    continue
                
                for item in os.listdir(current_dir):
                    item_path = os.path.join(current_dir, item)
                    if os.path.isdir(item_path):
                        dirs_to_scan.append(item_path)
                    elif item.lower().endswith(".zip"):
                        self.utils.extract_zip_file(item_path)
                        os.remove(item_path)
                        dirs_to_scan.append(os.path.splitext(item_path)[0])

            if "OpenCore" in product_name:
                oc_binary_data_zip_path = os.path.join(self.temporary_dir, "OcBinaryData.zip")
                print("")
                print(_("Please wait for download OcBinaryData..."))
                print(_("from {}").format(self.ocbinarydata_url))
                print("")
                self.fetcher.download_and_save_file(self.ocbinarydata_url, oc_binary_data_zip_path)

                if not os.path.exists(oc_binary_data_zip_path):
                    print("")
                    print(_("Could not download OcBinaryData at this time."))
                    print(_("Please try again later.") + "\n")
                    self.utils.request_input()
                    shutil.rmtree(self.temporary_dir, ignore_errors=True)
                    return False
                
                self.utils.extract_zip_file(oc_binary_data_zip_path)

            if self.move_bootloader_kexts_to_product_directory(product_name):
                self.integrity_checker.generate_folder_manifest(asset_dir, manifest_path)
                self._save_download_history(local_download_history, product_name, product_id, product_download_url, sha256_hash)

        shutil.rmtree(self.temporary_dir, ignore_errors=True)
        return True
    
    def get_kernel_patches(self, patches_name, patches_url):
        patches_cache_dir = os.path.join(self.ock_files_dir, "patches")
        self.utils.create_folder(patches_cache_dir)
        cache_file = os.path.join(patches_cache_dir, re.sub(r'[^a-zA-Z0-9_]', '_', patches_name) + ".plist")

        if os.path.exists(cache_file):
            try:
                cached_data = self.utils.read_file(cache_file)
                if isinstance(cached_data, dict) and "Kernel" in cached_data and "Patch" in cached_data["Kernel"]:
                    return cached_data["Kernel"]["Patch"]
            except:
                pass

        try:
            response = self.fetcher.fetch_and_parse_content(patches_url, "plist")

            if isinstance(response, dict):
                try:
                    self.utils.write_file(cache_file, response)
                except:
                    pass

            return response["Kernel"]["Patch"]
        except: 
            print("")
            print(_("Unable to download {} at this time").format(patches_name))
            print(_("from {}").format(patches_url))
            print("")
            if os.path.exists(cache_file):
                print(_("Using cached version."))
                try:
                    cached_data = self.utils.read_file(cache_file)
                    if isinstance(cached_data, dict) and "Kernel" in cached_data and "Patch" in cached_data["Kernel"]:
                        return cached_data["Kernel"]["Patch"]
                except:
                    pass
            print(_("Please try again later or apply them manually."))
            print("")
            self.utils.request_input()
            return []
        
    def gather_hardware_sniffer(self):
        if os_name == "Windows":
            return self._gather_hardware_sniffer_windows()
        elif os_name == "Darwin":
            return self._gather_hardware_sniffer_mac()
        return

    def _gather_hardware_sniffer_mac(self):
        sniffer_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "hardware_sniffer_mac.py")
        if os.path.exists(sniffer_path):
            return sniffer_path
        return

    def _gather_hardware_sniffer_windows(self):
        self.utils.head(_("Gathering Hardware Sniffer"))

        PRODUCT_NAME = "Hardware-Sniffer-CLI.exe"
        REPO_OWNER = "lzhoang2801"
        REPO_NAME = "Hardware-Sniffer"

        destination_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), PRODUCT_NAME)
        local_download_history = self._load_download_history()
        history_item = local_download_history.get(PRODUCT_NAME)

        if history_item is not None and os.path.exists(destination_path):
            local_hash = self.integrity_checker.get_sha256(destination_path)
            file_is_valid = (local_hash == history_item.get("sha256"))
            if file_is_valid:
                print("")
                print(_("Latest version of {} already downloaded.").format(PRODUCT_NAME))
                return destination_path
        
        latest_release = self.github.get_latest_release(REPO_OWNER, REPO_NAME) or {}
        
        product_id = None
        product_download_url = None
        sha256_hash = None

        asset_name = PRODUCT_NAME.split('.')[0]
        for asset in latest_release.get("assets", []):
            if asset.get("product_name") == asset_name:
                product_id = asset.get("id")
                product_download_url = asset.get("url")
                sha256_hash = asset.get("sha256")
                break

        if not all([product_id, product_download_url, sha256_hash]):
            if history_item is not None and os.path.exists(destination_path):
                print("")
                print(_("Could not check for updates for {}.").format(PRODUCT_NAME))
                print(_("Using cached version."))
                print("")
                return destination_path
            print("")
            print(_("Could not find release information for {}.").format(PRODUCT_NAME))
            print(_("Please try again later."))
            print("")
            self.utils.request_input()
            raise Exception(_("Could not find release information for {}.").format(PRODUCT_NAME))

        if history_item is not None:
            is_latest_id = (product_id == history_item.get("id"))
            if is_latest_id and os.path.exists(destination_path):
                print("")
                print(_("Latest version of {} already downloaded.").format(PRODUCT_NAME))
                return destination_path

        print("")
        print(_("Updating") if history_item is not None else _("Please wait for download"), end=" ")
        print(_("{}...").format(PRODUCT_NAME))
        print("")
        print(_("from {}").format(product_download_url))
        print("")
        
        if not self.fetcher.download_and_save_file(product_download_url, destination_path, sha256_hash):
            if os.path.exists(destination_path):
                print(_("Using cached version."))
                return destination_path
            manual_download_url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"
            print(_("Go to {} to download {} manually.").format(manual_download_url, PRODUCT_NAME))
            print("")
            self.utils.request_input()
            raise Exception(_("Failed to download {}.").format(PRODUCT_NAME))

        self._save_download_history(local_download_history, PRODUCT_NAME, product_id, product_download_url, sha256_hash)
        
        return destination_path
