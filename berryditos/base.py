#!/usr/bin/env python

from __future__ import print_function
import os
import sys
import shlex
import time
import signal
import zipfile
import subprocess
import glob
import errno
import threading
import re
import binascii
import shutil
import requests
try:
	from tempfile import TemporaryDirectory
except:
	import tempfile
	class TemporaryDirectory(object):
		"""
		Context manager for tempfile.mkdtemp().
		This class is available in python +v3.2.
		"""
		def __enter__(self):
			self.dir_name = tempfile.mkdtemp()
			return self.dir_name
		def __exit__(self, exc_type, exc_value, traceback):
			shutil.rmtree(self.dir_name)

if os.getuid() != 0:
	print("Berryditos must be run as root")
	exit()

try:
	rawinput = raw_input
except NameError:
	rawinput = input

DRYRUN = 1
__version__ = '0.0.3'

def dryrunnable(verbose=0):
	def dryrunnabledeco(f):
		def r(*a, **kw):
			return f(*a, **kw)
		def dr(*a, **kw):
			if verbose:
				print("{}: {}".format(f.__name__, ', '.join(list(a) + list(map(lambda x: '='.join(x), kw.items())))))
			if hasattr(f, '_drvalue'):
				return f._drvalue(a, kw)
		global DRYRUN
		if DRYRUN:
			return dr
		else:
			return r
	return dryrunnabledeco

def drvalue(g):
	def deco(f):
		setattr(f, '_drvalue', g)
		return f
	return deco

@dryrunnable()
def dd(t):
	args = shlex.split(t.strip('dd '))
	ddcmd = subprocess.Popen(['dd'] + args, stderr=subprocess.PIPE)
	while ddcmd.poll() is None:
		time.sleep(0.3)
		ddcmd.send_signal(signal.SIGUSR1)
		while 1:
			l = ddcmd.stderr.readline()
			if b'records in' in l:
				print(l[:l.index('+')], 'records')
			if b'bytes' in l:
				print(l.strip().decode()+'    ', end='\r')
				break
	print(ddcmd.stderr.read().decode())
	return 1

def delete_second_partition(fn):
	fh = open(fn, "r+b")
	fh.seek(462)
	fh.write(b'\x00'*16)
	fh.close()


def threadit(f, *a, **kw):
	run_thread = threading.Thread(None, f, None, a, kw)
	run_thread.start()
	return run_thread

@dryrunnable(1)
def oss(c, target=None):
	if c.startswith("dd "):
		return dd(c)
	r = subprocess.Popen(c, stdout=subprocess.PIPE, shell=True).stdout.read().decode('utf8')
	if target:
		target.value = r
	return r

def inputy(s):
	return rawinput(s + ' (y/n)? ') == 'y'

def lastraspbian():
	url = 'https://downloads.raspberrypi.org/raspbian/images/'
	c = requests.get(url).content.decode('utf-8')
	lastdate = sorted(re.findall('(raspbian-[0-9-]+)', c))[-1]
	cc = requests.get(url + lastdate).content.decode('utf-8')
	zipfilename = re.findall('([a-zA-Z0-9-]+.zip)', cc)[0]
	lastname = zipfilename[:-4]
	imgfile = lastname + '.img'

	images = map(lambda x: x[:-4], glob.glob("2*-raspbian-*.img") + glob.glob("2*-raspbian-*.zip"))
	images = list(set(images))
	print("In current folder: {} Raspbian image{}".format(len(images), 's'*int(len(images) > 1)))
	for im in images:
		print("  " + im)

	if lastname in images:
		unzipifnoimg(lastname)
		return imgfile
	else:
		if inputy('\nLast    = {}\nDownload and install last raspbian ({}) (needs around 6GB)'.format(zipfilename, lastdate)):
			oss('wget {}{}/{} -O {}'.format(url, lastdate, zipfilename, zipfilename))
			oss('unzip {}'.format(zipfilename))
			return imgfile
	if not images:
		print("No Raspian image found, exiting.")
		exit()
	r = choose_elem(images, "# of Raspbian image to install: ")
	return unzipifnoimg(r)

def unzipifnoimg(name):
	imgfile = name + '.img'
	zipfilename = name + '.zip'
	if not os.path.exists(imgfile):
		unzip(zipfilename, imgfile)
	return imgfile

def mkdir(dirname):
	try:
		os.mkdir(dirname)
	except OSError as exc:
		if exc.errno != errno.EEXIST:
			raise exc

def isInt(v):
	v = str(v).strip()
	return v == '0' or (v if v.find('..') > -1 else v.lstrip('-+').rstrip('0').rstrip('.')).isdigit()

def choose_elem(l, q=None):
	for i, elem in enumerate(l):
		print(" [{}]: {}".format(i, elem))
	n = rawinput(q or "# of wanted element: ")
	try:
		se = l[int(n)]
	except Exception as e:
		print("Choice '{}' not found, exiting. ({})".format(n, e))
		exit()
	if inputy("Do you confirm selected element: {}".format(se)):
		return se
	exit()

class DevicesList(object):
	def __init__(self):
		self.dn = list(filter(lambda x: x and not x.startswith('wwn-') and not x.strip('1234567890').endswith('-part'), oss('ls /dev/disk/by-id').split('\n')))
		self.dv = dict(map(lambda x: [x, os.path.realpath(os.path.join('/dev/disk/by-id', x))], self.dn))
		self.ds = open('/proc/partitions', 'r').read().split('\n')
	def p(self):
		devices = self.dv
		for i, (name, devfile) in enumerate(devices.items()):
			filename = devfile.split('/')[-1]
			size = self.devfiletosize(filename)
			print('[{}] {} Go    {}  {}'.format(i, "%6.1f"%size, filename, name))
	def choose(self, q):
		try:
			return self.dv[self.dn[int(rawinput(q))]]
		except Exception:
			return None
	def devfiletosize(self, f):
		try:
			return self.real_devfiletosize(f)
		except:
			return 0
	def real_devfiletosize(self, f):
		if f.startswith('/dev/'):
			f = f[5:]
		devsizes = self.ds
		r = list(filter(lambda x: x.endswith(f), devsizes))[0]
		r = list(filter(bool, r.split()))[2]
		return int(r)/1e6

def prepdl():
	raspbian_img = lastraspbian()
	raspbian_sdc = extract_bootpart(raspbian_img)
	return raspbian_img, raspbian_sdc

@dryrunnable()
@drvalue(lambda a, kw: a[0] + '.boot')
def extract_bootpart(img):
	bootimg = img + '.boot'
	blocksize = 512
	mbr = open(img, 'rb').read(512)
	tailleB = 512 * int(binascii.hexlify(mbr[446 + 16:446 + 2 * 16][8:12][::-1]), 16)
	taille = (tailleB//blocksize)
	oss('dd if={} of={} count={} bs={}'.format(img, bootimg, taille, blocksize))
	delete_second_partition(bootimg)
	return bootimg

class RPiImage(object):
	def __init__(self, d=None, img=None, bootonly=None, dryrun=True):
		self.dryrun = dryrun
		global DRYRUN
		old_dryrun = DRYRUN
		DRYRUN = self.dryrun

		self.image = img or lastraspbian()
		self.bootonusb = False
		if not d:
			d = device_choice('burning Rpi image {}'.format(self.image))
		self.ddev = '/dev/' + d if not d.startswith('/dev/') else d
		self.bootonly = bootonly
		self.work()

		DRYRUN = old_dryrun
	def s(self, t):
		oss(t)
	def part(self, n):
		return '{}{}{}'.format(self.ddev, "p"*int("mmcblk" in self.ddev), n)
	def umount_target(self):
		self.s('umount {}*'.format(self.ddev))
	def burn_image(self):
		self.s('dd bs=8M if={} of={}'.format(self.image, self.ddev))
	def umount_and_burn(self):
		self.umount_target()
		self.burn_image()
	def work(self):
		self.umount_and_burn()
		if 'mmcblk' not in self.ddev:
			if not self.bootonly and inputy("Burn a boot-to-sda2 partition on an SD card?"):
				newdev = 'sda2'
				self.bootonusb = newdev
				RPiImage(device_choice("SD boot card".format()), extract_bootpart(self.image), bootonly=newdev)
			else:
				if not inputy("\n\nWARNING: some RPi's can't run without a boot partition on the SD card\nPlease ensure that either yours can or you use a booting SD card. Continue"):
					exit()
		self.prepare_boot()
		self.prepare_system()
		print("Raspbian Image {} OK".format(self.image))
	def prepare_unused_boot(self, partition):
		self.s('mkdir {}/UNUSED'.format(partition))
		self.s('mv {}/* {}/UNUSED'.format(partition, partition))
		self.s('echo "This partition is not used because your RPi will boot on the SD boot partition, then will run the OS on {}" > {}/Why_this_partition_is_UNUSED.txt'.format(self.bootonusb, partition))
	def prepare_boot(self, part=None):
		with MountEnv(part or self.part(1), self.s, self.dryrun) as tempdir:
			if self.bootonusb:
				self.prepare_unused_boot(tempdir)
				return
			for c in ActionBoot.__subclasses__():
				action = c()
				if action.confirm(self):
					action.work(self, tempdir)
	def prepare_system(self, part=None):
		if self.bootonly:
			return
		with MountEnv(part or self.part(2), self.s, self.dryrun) as tempdir:
			for c in ActionSystem.__subclasses__():
				action = c()
				if action.confirm(self):
					action.work(self, tempdir)

class ActionBoot(object):
	pass
class ActionSystem(object):
	pass

class ActionAddSSH(ActionBoot):
	def confirm(self, rpi=None):
		return inputy("Activate SSH by default")
	def work(self, rpi, partition):
		rpi.s('touch {}/ssh'.format(partition))
class ActionChangeBootPartitionCmdlinetxt(ActionBoot):
	def confirm(self, rpi=None):
		return rpi.bootonly
	def work(self, rpi, partition):
		rpi.s("sed -i 's/mmcblk0p2/{}/' {}/cmdline.txt".format(rpi.bootonly, partition))

class ActionRegisterWifiAP(ActionSystem):
	def confirm(self, rpi=None):
		return inputy('Register Wifi access points')
	def work(self, rpi, partition):
		rpi.s('nano {}/etc/wpa_supplicant/wpa_supplicant.conf'.format(partition))
		rpi.s('nano {}/etc/network/interfaces'.format(partition))
class ActionFstabRaspiconfigUSBBoot(ActionSystem):
	def confirm(self, rpi=None):
		return rpi.bootonusb
	def work(self, rpi, partition):
		rpi.s("sed -i 's/mmcblk0p2/{}/' {}/etc/fstab".format(rpi.bootonusb, partition))
		rpi.s("sed -i 's/mmcblk0p/{}/' {}/usr/bin/raspi-config".format(rpi.bootonusb[:-1], partition))
		rpi.s("sed -i 's/mmcblk0/{}/' {}/usr/bin/raspi-config".format(rpi.bootonusb[:-1], partition))

class MountEnv(object):
	def __init__(self, device, size=None, no_except_if_empty=False):
		self.td = TemporaryDirectory()
		self.device = device
		self.s = size or oss
		self.except_if_empty = not no_except_if_empty
		self.dirname = None
	def __enter__(self):
		self.dirname = self.td.__enter__()
		self.s('mount {} {}'.format(self.device, self.dirname))
		if not glob.glob(self.dirname + '/*') and self.except_if_empty:
			self.__exit__(None, None, None)
			raise Exception("Mount point is empty")
		return self.dirname
	def __exit__(self, *a):
		self.s('umount {}'.format(self.dirname))
		r = self.td.__exit__(*a)
		return r

@dryrunnable()
@drvalue(lambda a, kw: '/dev/zda')
def device_choice(s):
	dl = DevicesList()
	dl.p()
	devusb = dl.choose('# for {}? '.format(s))
	if rawinput('\n\n  {}  =  {} ({} Go)\n\nThis device is going to be COMPLETELY ERASED, type "ok" if you are 100% sure this is what you want\nTHIS CANNOT BE UNDONE: '.format(s, devusb, round(dl.devfiletosize(devusb), 1))) != 'ok':
		print("\n\nYou must have typed 'ok' to continue: exiting")
		exit()
	return devusb

def print_help():
	print('''Berryditos is an interactive tool that can edit and burn Raspbian images.
It must be run as root to be able to burn images to devices with dd.

By default the dry run mode is activated, you will only see the commands and that would have been run.
To actually edit and burn images, run `berryditos live`
''')

def run(*a, **kw):
	if '--help' in sys.argv or 'help' in sys.argv:
		print_help()
		exit()
	kw['dryrun'] = 'live' not in sys.argv
	RPiImage(*a, **kw)

def unzip(fn, target_name):
	z = zipfile.ZipFile(fn)
	entry_name = target_name #z.filelist[0].filename
	entry_info = z.getinfo(entry_name)
	i = z.open(entry_name)
	o = open(target_name, 'wb')
	offset = 0
	prtpct = 0.1
	nxtpct = prtpct
	tz = time.time()
	while True:
		b = i.read(2**13)
		offset += len(b)
		pct = (float(offset)/float(entry_info.file_size) * 100.)
		if (pct - nxtpct)*(pct - nxtpct - prtpct) < 0:
			remaining = (time.time() - tz) * (100 / pct - 1)
			print("  {}%   [remaining: {} seconds]".format(round(pct, 1), int(remaining)), end='\r')
			nxtpct += prtpct
		if b == b'':
			break
		o.write(b)
	i.close()
	o.close()
	return

if __name__ == '__main__':
	run()
