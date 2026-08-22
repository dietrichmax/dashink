# The Kindle

Device setup for the wall panel. For the service itself, see the [README](../README.md).

Target: **KT2 (7th gen, 2014)** on `5.12.2.2`, the last firmware Amazon shipped for it. [This video](https://www.youtube.com/watch?v=IRW_EYDcW1o) walks the whole sequence; the steps below are what actually worked on this device.

Confirm the jailbreak method against the [jailbreak wizard](https://kindlemodding.org/jailbreak-wizard.html) using your serial and firmware. The published matrices disagree with each other for KT2.

**Order matters, and two steps exist only to stop the Kindle updating itself out of reach mid-process.** Keep it offline except where noted.

1. **Fill the disk** so it cannot auto-update ([guide](https://kindlemodding.org/jailbreaking/prevent-auto-update/), default options).
2. **[WinterBreak](https://github.com/KindleModding/WinterBreak)**: copy to the Kindle root, eject, unplug, turn **airplane mode on**, reboot.
3. Open the Kindle Store, then turn airplane mode **off** so wifi comes up.
4. Tap the WinterBreak icon. That is root.
5. **[Hotfix](https://github.com/KindleModding/Hotfix)**: download `uptodate_hotfix_universal.bin` from releases and copy it to the Kindle root.
6. Eject, then Settings → Device Options → **Update Your Kindle**. It reboots and installs.
7. Tap **Run Hotfix** in the library, once. The entry can be deleted afterwards.
8. **MRPI and KUAL**, both from [MobileRead thread 225030](https://www.mobileread.com/forums/showthread.php?t=225030):
   - `KUAL-c6ac782-20250419.tar.xz`: the **coplate** build is the one that works here; the plain one does not.
   - `kual-mrinstaller-1.7.N-r19303.tar.xz`
9. MRPI first: extract, and move `extensions/` and `mrpackages/` into the Kindle root.
10. Then KUAL: drag `Update_KUALBooklet_hotfix_c6ac782_install.bin` to the root, eject, and run **Update Your Kindle** again. Another reboot.
11. KUAL now appears in the library as a book. It is the launcher for GTK extensions, not for the scripts in this repo, which the Hotfix's `sh_integration` picks up straight from `/mnt/us/documents/`.
12. **renameotabin**: [MobileRead post](https://www.mobileread.com/forums/showpost.php?p=4076733&postcount=25), `renameotabin.zip`. Unzip, move the folder into `extensions/`, open KUAL, run it and choose rename. It reboots. This is what permanently blocks OTA updates, and an update is the one remaining way to lose the jailbreak.
13. **USBNetwork**, for SSH. Same [MobileRead thread](https://www.mobileread.com/forums/showthread.php?t=225030) as KUAL, with a useful [writeup](https://blog.znjoa.com/2023/07/26/installing-usbnetwork-on-kindle/). Take `Update_usbnet_0.22.N_install_pw2_and_up.bin`: `pw2_and_up` is the device target and covers every modern 5.x Kindle including KT2, so it is the right file despite the Paperwhite name. Put it in `mrpackages/` on the root, then KUAL → Helper → Install MR Packages → USBNetwork.

    **Configure it over USB mass storage; no shell needed.** `/mnt/us` *is* the drive your computer mounts, so usbnet's files sit in `usbnet/etc` on it:

    - `config`: set `USE_WIFI=TRUE`. A wall-mounted panel is never plugged in, so USB networking is useless here; with this it answers on its normal LAN address instead.
    - `authorized_keys`: append your public key. It must go **here**, not in `~/.ssh/`: the rootfs is read-only and usbnet does not read the standard location, so `ssh-copy-id` cannot work. One key per line, as many as you like.

    Eject, then `;un` in the search bar starts the server.

    **The root password is not empty on this build**, whatever the writeups say, so key auth is the way in rather than a convenience. Set it up before you need it.

    On the client, `IdentitiesOnly` is what stops ssh offering your default keys first and prompting for their passphrase:

    ```
    Host kindle
      HostName 192.168.0.0        # the address info.sh printed
      User root
      IdentityFile ~/.ssh/id_kindle
      IdentitiesOnly yes
    ```

14. Copy [`kindle/`](../kindle/)`*.sh` to `/mnt/us/documents/`. With SSH working this no longer means plugging the Kindle in:

    ```bash
    ssh kindle 'cat > /mnt/us/documents/dashink.sh' < kindle/dashink.sh
    ssh kindle 'cat > /mnt/us/documents/restore.sh' < kindle/restore.sh
    ssh kindle 'cat > /mnt/us/documents/info.sh'    < kindle/info.sh
    ```

    Piped through `cat` rather than `scp`, because dropbear here has no `scp` binary on the far side, and this copies bytes exactly so nothing rewrites the line endings on the way.

    **Point it at your server.** The default is `http://dashink.lan:8099/dash.png`, so if your LAN DNS resolves `dashink.lan` there is nothing to configure. Otherwise put the address in `/mnt/us/dashink.conf`:

    ```sh
    DASHINK_URL=http://192.168.1.10:8099/dash.png
    DASHINK_INTERVAL=300
    ```

    That file is on the volume your computer mounts, so it is editable by plugging the Kindle in, with no shell. Keep it **out** of the script: deploying is a plain overwrite, so anything set inside `dashink.sh` is lost the next time you update it. Any `DASHINK_*` the script reads can be set here.

    **Check it parses before trusting it**, especially from a Windows checkout. Check `restore.sh` first, since it is the escape hatch:

    ```bash
    ssh kindle 'sh -n /mnt/us/documents/restore.sh && echo ok'
    ssh kindle 'sh -n /mnt/us/documents/dashink.sh && echo ok'
    ```

    busybox `sh` fails on CRLF with `syntax error: unexpected end of file`, blaming the last line rather than the real cause, and a script launched with `nohup ... &` reports only a quiet `Done(2)` that is easy to miss. `.gitattributes` pins `*.sh` to LF, but attributes apply at checkout, so a working copy predating them keeps whatever `core.autocrlf` wrote. `git add --renormalize .` fixes those.

    Start and stop it over SSH too. `dropbear` is independent of the reader UI, so it survives `dashink.sh` stopping `lab126_gui`:

    ```bash
    ssh kindle 'nohup sh /mnt/us/documents/dashink.sh > /dev/null 2>&1 < /dev/null &'
    ssh kindle 'sh /mnt/us/documents/restore.sh'
    ```

## Optional

None of these are needed to run dashink. The three scripts use only firmware tools (`eips`, `lipc-get-prop`, `lipc-set-prop`, `start`, `stop`, `ifconfig`) and busybox builtins, and `dashink.sh` falls back to `wget` where `curl` is absent, so there is nothing to install.

- **`disable_ads.sh`**, if the device carries Special Offers. From [notmarek's scriptlets](https://scriptlets.notmarek.com/). Drop it in `/mnt/us/documents/` and tap it. Ads appear in the gaps before the loop starts and after `restore.sh`. This is the one most people will actually want.
- **[kterm](https://github.com/bfabiszewski/kterm)**: a GTK terminal with an on-screen keyboard. Copy into `extensions/` and launch from KUAL. Packages at [fabiszewski.net](https://www.fabiszewski.net/kindle-terminal/). Useful for poking at the device before SSH works, but see the warning below: it is not a recovery path.
- **[KPM](https://github.com/gingrspacecadet/kpm)**, a package manager, *not* bundled with the Hotfix. Installed from inside kterm, which is the only reason kterm would need to come first:

  ```sh
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/gingrspacecadet/kpm/main/install-kpm.sh)"
  ```

  Note the circularity: that installer needs `curl` already on the device, so it cannot help in the one case where a package manager would. Invoked afterwards with `;kpm` in the search bar.

KUAL after the sequence above, with the optional kterm, USBNetwork and the OTA blocker installed:

![the KUAL launcher](kual.jpg)

The three dashink scripts now show in the library:

| Entry | |
|---|---|
| `dashink.sh` | stops the reader UI, begins the fetch/draw loop |
| `restore.sh` | kills the loop, restarts `lab126_gui` |
| `info.sh` | panel geometry, wifi address and a test fetch. Safe: it leaves the reader UI up |

![dashink.sh and restore.sh as library entries](library.jpg)

Start with `info.sh`. It is the only diagnostic that works before SSH does.

> **kterm is not the recovery path for the dashboard.** It is a framework app, so once `dashink.sh` stops `lab126_gui` it cannot be launched, precisely when you would reach for it. Use it for setup, and to test `restore.sh` before trusting it. Once the loop is running the only ways back are SSH or holding power ~20s, which is why USBNetwork or an SSH package still matters before you wire anything into boot.

The Hotfix draws via **FBInk** because `eips` is deprecated on newer firmware. `eips` still works on 5.12.2.2, so `dashink.sh` uses it. If the image ever fails to draw or renders wrong, `fbink -g file=/tmp/dashink.png` is the maintained equivalent and is already on the device.

Serve over **plain HTTP**. The 2014 TLS stack will not validate a modern certificate chain, and this is LAN-only traffic.
