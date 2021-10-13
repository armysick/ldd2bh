#!/usr/bin/env python3

import os, sys, uuid, argparse, textwrap, glob, json, base64
from datetime import datetime
from binascii import b2a_hex

hvt = ["512", "516", "519", "520"]

db = {}

# https://docs.microsoft.com/en-us/troubleshoot/windows-server/identity/useraccountcontrol-manipulate-account-properties
user_access_control = {
	"SCRIPT": 0x0001,
	"ACCOUNTDISABLE": 0x0002,
	"HOMEDIR_REQUIRED": 0x0008,
	"LOCKOUT": 0x0010,
	"PASSWD_NOTREQD": 0x0020,
	"PASSWD_CANT_CHANGE": 0x0040,
	"ENCRYPTED_TEXT_PWD_ALLOWED": 0x0080,
	"TEMP_DUPLICATE_ACCOUNT": 0x0100,
	"NORMAL_ACCOUNT": 0x0200,
	"INTERDOMAIN_TRUST_ACCOUNT": 0x0800,
	"WORKSTATION_TRUST_ACCOUNT": 0x1000,
	"SERVER_TRUST_ACCOUNT": 0x2000,
	"DONT_EXPIRE_PASSWORD": 0x10000,
	"MNS_LOGON_ACCOUNT": 0x20000,
	"SMARTCARD_REQUIRED": 0x40000,
	"TRUSTED_FOR_DELEGATION": 0x80000,
	"NOT_DELEGATED": 0x100000,
	"USE_DES_KEY_ONLY": 0x200000,
	"DONT_REQ_PREAUTH": 0x400000,
	"PASSWORD_EXPIRED": 0x800000,
	"TRUSTED_TO_AUTH_FOR_DELEGATION": 0x1000000,
	"PARTIAL_SECRETS_ACCOUNT": 0x04000000
}

def ret_os_path():
	if ((sys.platform == 'win32') and (os.environ.get('OS','') == 'Windows_NT')):
		return "\\"
	else:
		return "/"

class User:

	def __init__(self):
		self.AllowedToDelegate = []
		self.ObjectIdentifier = ""
		self.PrimaryGroupSid = ""
		self.properties = {
			"name": None,
			"domain": None,
			"objectid": None,
			"distinguishedname": None,
			"highvalue": None,
			"unconstraineddelegation": None,
			"passwordnotreqd": None,
			"enabled": None,
			"lastlogon": None,
			"lastlogontimestamp": None,
			"pwdlastset": None,
			"dontreqpreauth": None,
			"pwdneverexpires": None,
			"sensitive": None,
			"serviceprincipalnames": [],
			"hasspn": None,
			"displayname": None,
			"email": None,
			"title": None,
			"homedirectory": None,
			"description": None,
			"userpassword": None,
			"admincount": None,
			"sidhistory": []
		}
		self.Aces = []
		self.SPNTargets = []
		self.HasSIDHistory = []

	def export(self):
		buf = '{' + '"AllowedToDelegate": {}, "ObjectIdentifier": "{}", "PrimaryGroupSid": "{}", "Properties": {}, "Aces": {}, "SPNTargets": {}, "HasSIDHistory": {}'.format(
			self.AllowedToDelegate,
			self.ObjectIdentifier,
			self.PrimaryGroupSid,
			self.properties,
			self.Aces,
			self.SPNTargets,
			self.HasSIDHistory
			) + '}'
		return buf.replace("'", '"').replace("`", "'").replace("True", "true").replace("False", "false").replace("None", "null")

class Computer:

	def __init__(self):
		self.ObjectIdentifier = ""
		self.AllowedToAct = []
		self.PrimaryGroupSid = ""
		self.LocalAdmins = []
		self.PSRemoteUsers = []
		self.properties = {
			"name": None,
			"objectid": None,
			"domain": None,
			"highvalue": None,
			"distinguishedname": None,
			"unconstraineddelegation": None,
			"enabled": None,
			"haslaps": None,
			"lastlogontimestamp": None,
			"pwdlastset": None,
			"serviceprincipalnames": [],
			"description": None,
			"operatingsystem": None
		}
		self.RemoteDesktopUsers = []
		self.DcomUsers = []
		self.AllowedToDelegate = []
		self.Sessions = []
		self.Aces = []

	def export(self):
		buf = '{' + '"ObjectIdentifier": "{}", "AllowedToAct": {}, "PrimaryGroupSid": "{}", "LocalAdmins": {}, "PSRemoteUsers": {}, "Properties": {}, "RemoteDesktopUsers": {}, "DcomUsers": {}, "AllowedToDelegate": {}, "Sessions": {}, "Aces": {}'.format(
			self.ObjectIdentifier,
			self.AllowedToAct,
			self.PrimaryGroupSid,
			self.LocalAdmins,
			self.PSRemoteUsers,
			self.properties,
			self.RemoteDesktopUsers,
			self.DcomUsers,
			self.RemoteDesktopUsers,
			self.AllowedToDelegate,
			self.Sessions,
			self.Aces,
			) + '}'
		return buf.replace("'", '"').replace("True", "true").replace("False", "false").replace("None", "null")

class Group:

	def __init__(self):
		self.ObjectIdentifier = None
		self.properties = {
			"domain": None,
			"objectid": None,
			"highvalue": None,
			"name": None,
			"distinguishedname": None,
			"admincount": None,
			"description": None
		}
		self.Members = []
		self.Aces = []

	def export(self):
		#self.sanitize()
		buf = '{' + '"ObjectIdentifier": "{}", "Properties": {}, "Members": {}, "Aces": {}'.format(
			self.ObjectIdentifier,
			str(json.dumps(self.properties)),
			self.Members,
			self.Aces
			) + '}'
		return buf.replace("'", '"').replace("`", "'").replace("True", "true").replace("False", "false").replace("None", "null")

class Domain:

	def __init__(self):
		self.ObjectIdentifier = None
		self.properties = {
			"name": None,
			"domain": None,
			"highvalue": True,
			"objectid": None,
			"distinguishedname": None,
			"description": None,
			"functionallevel": None
		}
		self.Trusts = []
		self.Aces = []
		self.Links = []
		self.Users = []
		self.Computers = []
		self.ChildOus = []

	def export(self):
		buf = '{' + '"ObjectIdentifier": "{}", "Properties": {}, "Trusts": {}, "Aces": {}, "Links": {}, "Users": {}, "Computers": {}, "ChildOus": {}'.format(
			self.ObjectIdentifier,
			self.properties,
			self.Trusts,
			self.Aces,
			self.Links,
			self.Users,
			self.Computers,
			self.ChildOus
			) + '}'
		return buf.replace("'", '"').replace("`", "'").replace("True", "true").replace("False", "false").replace("None", "null")

def check(attr, mask):
	if ((attr & mask) > 0):
		return True
	return False

def to_epoch(longform):
	# 2021-09-30 05:28:09.685524+00:00
	try:
		utc_time = datetime.strptime(longform, "%Y-%m-%d %H:%M:%S.%f+00:00")
		epoch_time = int((utc_time - datetime(1970, 1, 1)).total_seconds())
		return int(epoch_time)
	except ValueError:
		return -1

def parse_users(input_folder, output_folder):
	count = 0
	j = json.loads(open(input_folder + ret_os_path() + "domain_users.json", "r").read())
	buf = '{"users": ['
	for user in j:
		u = User()
		u.ObjectIdentifier = user['attributes']['objectSid'][0]
		u.PrimaryGroupSid = '-'.join(user['attributes']['objectSid'][0].split("-")[:-1]) + "-" + str(user['attributes']['primaryGroupID'][0])

		if 'userPrincipalName' in user['attributes'].keys():
			u.properties['name'] = str(user['attributes']['userPrincipalName'][0]).upper()
		else:
			u.properties['name'] = str(user['attributes']['distinguishedName'][0]).split(",CN=")[0].split("=")[1].upper() + "@" + '.'.join(str(user['attributes']['distinguishedName'][0]).split(",DC=")[1:]).upper()

		if 'userPrincipalName' in user['attributes'].keys():
			u.properties['domain'] = str(user['attributes']['userPrincipalName'][0]).upper().split("@")[1]
		else:
			u.properties['domain'] = str(u.properties["name"]).upper().split("@")[1]

		u.properties['objectid'] = user['attributes']['objectSid'][0]
		u.properties['distinguishedname'] = user['attributes']['distinguishedName'][0].replace('"', '`').replace("'", "`")

		if ("$" in u.properties['distinguishedname']):
			db[u.properties['distinguishedname']] = [u.ObjectIdentifier, "Computer"]
		else:
			db[u.properties['distinguishedname']] = [u.ObjectIdentifier, "User"]

		u.properties['highvalue'] = False
		for h in hvt:
			if (h in str(user['attributes']['primaryGroupID'][0])):
				u.properties['highvalue'] = True


		u.properties['unconstraineddelegation'] = False
		if check(user['attributes']['userAccountControl'][0], user_access_control['TRUSTED_FOR_DELEGATION']):
			u.properties['unconstraineddelegation'] = True

		# PASSWD_NOTREQD = 0x0020
		u.properties["passwordnotreqd"] = False
		if check(user['attributes']['userAccountControl'][0], user_access_control['PASSWD_NOTREQD']):
			u.properties["passwordnotreqd"] = True

		# ACCOUNTDISABLE = 0x0002
		u.properties["enabled"] = False
		if (not check(user['attributes']['userAccountControl'][0], user_access_control['ACCOUNTDISABLE'])):
			u.properties['enabled'] = True

		if 'lastLogon' in user['attributes'].keys():
			u.properties['lastlogon'] = to_epoch(user['attributes']['lastLogon'][0])
		else:
			u.properties['lastlogon'] = -1

		if 'lastLogonTimestamp' in user['attributes'].keys():
			u.properties['lastlogontimestamp'] = to_epoch(user['attributes']['lastLogonTimestamp'][0])
		else:
			u.properties['lastlogontimestamp'] = -1

		if 'pwdLastSet' in user['attributes'].keys():
			u.properties['pwdlastset'] = to_epoch(user['attributes']['pwdLastSet'][0])
		else:
			u.properties['pwdlastset'] = -1

		u.properties['dontreqpreauth'] = False
		if check(user['attributes']['userAccountControl'][0], user_access_control['DONT_REQ_PREAUTH']):
			u.properties["dontreqpreauth"] = True

		u.properties['pwdneverexpires'] = False
		if check(user['attributes']['userAccountControl'][0], user_access_control['DONT_EXPIRE_PASSWORD']):
			u.properties["pwdneverexpires"] = True

		u.properties['sensitive'] = False
		u.properties['serviceprincipalnames'] = []
		
		if 'servicePrincipalName' in user['attributes'].keys():
			u.properties['hasspn'] = user['attributes']['servicePrincipalName'][0]
		else:
			u.properties['hasspn'] = False

		if 'displayName' in user['attributes'].keys():
			u.properties['displayname'] = user['attributes']['displayName'][0].replace('"', '`').replace("'", "`")
		else:
			u.properties['displayname'] = user['attributes']['sAMAccountName'][0].replace('"', '`').replace("'", "`")

		u.properties['email'] = None
		u.properties['title'] = None
		u.properties['homedirectory'] = None

		if 'description' in user['attributes'].keys():
			u.properties['description'] = user['attributes']['description'][0].replace('"', '`').replace("'", "`")
		else:
			u.properties['description'] = None

		u.properties['userpassword'] = None

		if 'adminCount' in user['attributes'].keys():
			u.properties['admincount'] = True
		else:
			u.properties['admincount'] = False

		u.properties['sidhistory'] = []

		u.Aces = []
		u.SPNTargets = []
		u.HasSIDHistory = []

		buf += u.export() + ', '
		count += 1

	buf = buf[:-2] + '],' + ' "meta": ' + '{' + '"type": "users", "count": {}, "version": 3'.format(count) + '}}'

	with open(output_folder + ret_os_path() + "users.json", "w") as outfile:
		outfile.write(buf)
	buf = ""

def build_la_dict(domain_sid, group_sid, member_type):
	return { "MemberId" : domain_sid + '-' + group_sid, "MemberType": member_type }

def parse_computers(input_folder, output_folder):
	count = 0
	j = json.loads(open(input_folder + ret_os_path() + "domain_computers.json", "r").read())
	buf = '{"computers": ['
	for comp in j:
		c = Computer()
		c.ObjectIdentifier = comp['attributes']['objectSid'][0]
		c.AllowedToAct = []
		c.PrimaryGroupSid = '-'.join(comp['attributes']['objectSid'][0].split("-")[:-1]) + "-" + str(comp['attributes']['primaryGroupID'][0])

		sid = '-'.join(comp['attributes']['objectSid'][0].split("-")[:-1])
		c.LocalAdmins = []
		c.LocalAdmins.append(build_la_dict(sid, "519", "Group"))
		c.LocalAdmins.append(build_la_dict(sid, "512", "Group"))
		c.LocalAdmins.append(build_la_dict(sid, "500", "User"))

		c.PSRemoteUsers = []

		if 'userPrincipalName' in comp['attributes'].keys():
			c.properties["name"] = str(comp['attributes']['userPrincipalName'][0]).upper()
		else:
			c.properties["name"] = str(comp['attributes']['distinguishedName'][0]).split(",CN=")[0].split("=")[1].replace(",OU", "") + "." + '.'.join(str(comp['attributes']['distinguishedName'][0]).split(",DC=")[1:]).upper()

		if 'userPrincipalName' in comp['attributes'].keys():
			c.properties["domain"] = str(comp['attributes']['userPrincipalName'][0]).upper().split(".")[1]
		else:
			c.properties["domain"] = str(c.properties["name"]).upper().split(".")[1]

		c.properties["objectid"] = comp['attributes']['objectSid'][0]

		c.properties["distinguishedname"] = comp['attributes']['distinguishedName'][0].replace('"', '`').replace("'", "`")

		c.properties["highvalue"] = False
		for h in hvt:
			if (h in str(comp['attributes']['primaryGroupID'][0])):
				c.properties["highvalue"] = True

		if 'userAccountControl' in comp['attributes'].keys():
			if check(comp['attributes']['userAccountControl'][0], user_access_control['TRUSTED_FOR_DELEGATION']):
				c.properties['unconstraineddelegation'] = True
		else:
			c.properties['unconstraineddelegation'] = False


		c.properties["enabled"] = False
		if (not check(comp['attributes']['userAccountControl'][0], user_access_control['ACCOUNTDISABLE'])):
			c.properties['enabled'] = True

		c.properties['haslaps'] = False # TDODO

		if 'lastLogonTimestamp' in comp['attributes'].keys():
			c.properties['lastlogontimestamp'] = to_epoch(comp['attributes']['lastLogonTimestamp'][0])
		else:
			c.properties['lastlogontimestamp'] = -1

		if 'pwdLastSet' in comp['attributes'].keys():
			c.properties['pwdlastset'] = to_epoch(comp['attributes']['pwdLastSet'][0])
		else:
			c.properties['pwdlastset'] = -1

		if 'servicePrincipalName' in comp['attributes'].keys():
			c.properties['serviceprincipalnames'] = comp['attributes']['servicePrincipalName']
		else:
			c.properties['serviceprincipalnames'] = None

		if 'description' in comp['attributes'].keys():
			c.properties['description'] = comp['attributes']['description'][0].replace('"', '`').replace("'", "`")
		else:
			c.properties['description'] = None

		if 'operatingSystem' in comp['attributes'].keys():
			c.properties['operatingsystem'] = comp['attributes']['operatingSystem']
		else:
			c.properties['operatingsystem'] = None

		buf += c.export() + ', '
		count += 1

	buf = buf[:-2] + '],' + ' "meta": ' + '{' + '"type": "computers", "count": {}, "version": 3'.format(count) + '}}'

	with open(output_folder + ret_os_path() + "computers.json", "w") as outfile:
		outfile.write(buf)
	buf = ""

def build_mem_dict(sid, member_type):
	return { "MemberId" : sid, "MemberType": member_type }

def parse_groups(input_folder, output_folder, no_users):
	count = 0

	if (no_users):
		j = json.loads(open(input_folder + ret_os_path() + "domain_users.json", "r").read())
		for user in j:
			u = user['attributes']['distinguishedName'][0].replace('"', '`').replace("'", "`")
			if ("$" in u):
				db[u] = [user['attributes']['objectSid'][0], "Computer"]
			else:
				db[u] = [user['attributes']['objectSid'][0], "User"]

	j = json.loads(open(input_folder + ret_os_path() + "domain_groups.json", "r").read())

	# fist build up group sids
	for group in j:
		db[group['attributes']['distinguishedName'][0]] = [group['attributes']['objectSid'][0], "Group"]

	buf = '{"groups": ['
	# now build up the whole file
	f = open(output_folder + ret_os_path() + "groups.json", "w")
	for group in j:
		g = Group()
		g.ObjectIdentifier = group['attributes']['objectSid'][0]

		if 'userPrincipalName' in group['attributes'].keys():
			g.properties['name'] = str(group['attributes']['userPrincipalName'][0]).upper().replace('"', '`').replace("'", "`")
		else:
			g.properties['name'] = str(group['attributes']['distinguishedName'][0]).split(",CN=")[0].split("=")[1].replace(",OU", "").replace('"', '`').replace("'", "`").upper() + "@" + '.'.join(str(group['attributes']['distinguishedName'][0]).split(",DC=")[1:]).upper().replace('"', '`').replace("'", "`")

		if 'userPrincipalName' in group['attributes'].keys():
			g.properties['domain'] = str(group['attributes']['userPrincipalName'][0]).upper().split("@")[1]
		else:
			g.properties['domain'] = str(g.properties["name"]).upper().split("@")[1].replace('"', '`').replace("'", "`")

		g.properties['objectid'] = group['attributes']['objectSid'][0]

		g.properties['highvalue'] = False
		for h in hvt:
			if (h in str(group['attributes']['objectSid'][0]).split("-")[-1:]):
				g.properties['highvalue'] = True

		g.properties['distinguishedname'] = group['attributes']['distinguishedName'][0].replace('"', '`').replace("'", "`")

		if 'adminCount' in group['attributes'].keys():
			g.properties['admincount'] = True
		else:
			g.properties['admincount'] = False

		if 'description' in group['attributes'].keys():
			g.properties['description'] = group['attributes']['description'][0].replace('"', '`').replace("'", "`")
		else:
			g.properties['description'] = None

		try:
			for m in group['attributes']['member']:
				t = db[m]
				g.Members.append(build_mem_dict(t[0], t[1]))
		except:
			pass

		count += 1
		if (count < len(j)):
			buf += g.export() + ', '
		else:
			buf += g.export()
		f.write(buf)
		buf = ""

	buf = '],' + ' "meta": ' + '{' + '"type": "groups", "count": {}, "version": 3'.format(count) + '}}'
	f.write(buf)
	f.close()

# https://stackoverflow.com/questions/33188413/python-code-to-convert-from-objectsid-to-sid-representation
def sid_to_str(sid):
	try:
		# Python 3
		if str is not bytes:
			# revision
			revision = int(sid[0])
			# count of sub authorities
			sub_authorities = int(sid[1])
			# big endian
			identifier_authority = int.from_bytes(sid[2:8], byteorder='big')
			# If true then it is represented in hex
			if identifier_authority >= 2 ** 32:
				identifier_authority = hex(identifier_authority)

			# loop over the count of small endians
			sub_authority = '-' + '-'.join([str(int.from_bytes(sid[8 + (i * 4): 12 + (i * 4)], byteorder='little')) for i in range(sub_authorities)])
		# Python 2
		else:
			revision = int(b2a_hex(sid[0]))
			sub_authorities = int(b2a_hex(sid[1]))
			identifier_authority = int(b2a_hex(sid[2:8]), 16)
			if identifier_authority >= 2 ** 32:
				identifier_authority = hex(identifier_authority)

			sub_authority = '-' + '-'.join([str(int(b2a_hex(sid[11 + (i * 4): 7 + (i * 4): -1]), 16)) for i in range(sub_authorities)])
		objectSid = 'S-' + str(revision) + '-' + str(identifier_authority) + sub_authority

		return objectSid
	except Exception:
		pass

def parse_domains(input_folder, output_folder):
	count = 0
	sid = None
	j = json.loads(open(input_folder + ret_os_path() + "domain_trusts.json", "r").read())
	buf = '{"domains": ['
	for dom in j:
		d = Domain()
		if ("base64".upper() in dom['attributes']['securityIdentifier'][0]['encoding'].upper()):
			sid = sid_to_str(base64.b64decode(dom['attributes']['securityIdentifier'][0]['encoded']))
			d.ObjectIdentifier = sid
		else:
			d.ObjectIdentifier = None
		d.properties['name'] = dom['attributes']['name'][0].upper()
		d.properties['domain'] = dom['attributes']['cn'][0].upper()
		d.properties['objectid'] = sid
		d.properties['distinguishedname'] = dom['attributes']['distinguishedName'][0].upper()

		if 'description' in dom['attributes'].keys():
			d.properties['description'] = dom['attributes']['description'][0].replace('"', '`').replace("'", "`")
		else:
			d.properties['description'] = None

		if 'msds-behavior-version' in dom['attributes'].keys():
			d.properties['functionallevel'] = dom['attributes']['msds-behavior-version'][0]
		else:
			d.properties['functionallevel'] = None

		buf += d.export() + ', '
		count += 1

	buf = buf[:-2] + '],' + ' "meta": ' + '{' + '"type": "domains", "count": {}, "version": 3'.format(count) + '}}'

	with open(output_folder + ret_os_path() + "domains.json", "w") as outfile:
		outfile.write(buf)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(
			formatter_class=argparse.RawDescriptionHelpFormatter,
			description='Convert ldapdomaindump to Bloodhound',
			epilog=textwrap.dedent('''Examples:\npython3 ldd2bh.py -i ldd -o bh''')
	)

	parser.add_argument('-i','--input', dest="input_folder", default=".", required=False, help='Input Directory for ldapdomaindump data, default: current directory')
	parser.add_argument('-o','--output', dest="output_folder", default=".", required=False, help='Output Directory for Bloodhound data, default: current directory')
	parser.add_argument('-a','--all', action='store_true', default=True, required=False, help='Output only users, default: True')
	parser.add_argument('-u','--users', action='store_true', default=False, required=False, help='Output only users, default: False')
	parser.add_argument('-c','--computers', action='store_true', default=False, required=False, help='Output only computers, default: False')
	parser.add_argument('-g','--groups', action='store_true', default=False, required=False, help='Output only groups, default: False')
	parser.add_argument('-d','--domains', action='store_true', default=False, required=False, help='Output only domains, default: False')

	args = parser.parse_args()

	if ((args.input_folder != ".") and (args.output_folder != ".")):
		if (sum([args.users, args.computers, args.groups, args.domains]) == 0):
			args.users = True
			args.computers = True
			args.groups = True
			args.domains = True
		if (args.users):
			print("Parsing users...")
			parse_users(args.input_folder, args.output_folder)
		if (args.computers):
			print("Parsing computers...")
			parse_computers(args.input_folder, args.output_folder)
		if (args.groups):
			print("Parsing groups...")
			parse_groups(args.input_folder, args.output_folder, not args.users)
		if (args.domains):
			print("Parsing domains...")
			parse_domains(args.input_folder, args.output_folder)
		print("Done!")
	else:
		parser.print_help()
