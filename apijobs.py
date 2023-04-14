import tempfile
import sys
import os
import subprocess
import re
import argparse
import yaml
from zoautil_py import datasets, mvscmd, opercmd, jobs
from zoautil_py.types import DDStatement, DatasetDefinition, FileDefinition, Dataset

def parse_our_args(argv=None):
    """
      parse args
    """

    global opts
    program_name = os.path.basename(sys.argv[0])
    if argv is None:
        argv = sys.argv[1:]

    try:
        parser = argparse.ArgumentParser(program_name)
        parser.add_argument("-yaml",
                            "--operational_yaml_file",
                            help="YAML Input",
                            required=False)
        opts = parser.parse_args(argv)

        opts.program_name = program_name

        opts.max_rc = 0
        opts.script_dir = os.path.dirname(os.path.abspath(__file__))

        if opts.operational_yaml_file is None:
            _default_operational_yaml_file = "apijobs.yaml"
            opts.operational_yaml_file = opts.script_dir + '/' + _default_operational_yaml_file



    except Exception as exp:
        sys.stderr.write(program_name, exp, '\n')
        sys.stderr.write('for help use --help\n')
        if opts.max_rc < 16:
            opts.max_rc = 16
        sys.exit(16)


def load_yaml_file(yaml_file):
    """
    load yaml
    """
    global opts
    # Open the yaml file and load the data into defaults
    with open(yaml_file,encoding="cp037") as file:
        _yamldata = yaml.safe_load(file)
    return _yamldata






def run_job(jobname):
    """
      run job
    """

    global opts
    _ddlist = []
    _sysin_data = ''

    opts.jobpgm = opts.operational_yaml["JOBS"][jobname]["PGM"]
    opts.ddlist = opts.operational_yaml["JOBS"][jobname]["DDLIST"]
    opts.pgmparm = opts.operational_yaml["JOBS"][jobname]["PGMPARM"]
    opts.pgmauth = opts.operational_yaml["JOBS"][jobname]["PGMAUTH"]

    if opts.pgmparm == "None":
        opts.pgmparm = ''
    _del_file_name_list = []
    newdsname = ''
    ddatr = {}

    for ddstmt in opts.ddlist:

        for dds,atrs in ddstmt.items():
            for atr_elem in atrs:
                if ddstmt[dds][atr_elem] != "None":
                    if "&" in ddstmt[dds][atr_elem]:
                        for findsim in ddstmt[dds][atr_elem].split('.'):
                            if not findsim:
                                continue
                            if findsim[0] == '&':
                                symname = findsim
                                print(f"Looking up Symbol:{symname}")
                                symlist = subprocess.run(["opercmd", "d symbols"],
                                                         capture_output=True,
                                                         text=True,
                                                         check=True)
                                for syssym in symlist.stdout.splitlines():
                                    if symname in syssym:
                                        symname_value = syssym.split()[2].strip('"')
                                        findsim = symname_value
                                print(f"findsim value: {findsim}")
                            newdsname += findsim+"."
                        ddstmt[dds][atr_elem] = newdsname.strip('.')
                    ddatr[atr_elem] = ddstmt[dds][atr_elem]

        for ddname in ddstmt.keys():

            temphlq = opts.operational_yaml['GLOBALS']['TEMPHLQ']

            if ddstmt[ddname]['type'] == "seq":
                if ddstmt[ddname]['dataset_name'] == "None":
                    _dd_file = datasets.tmp_name(datasets.hlq(temphlq))
                    _del_file_name_list.append(_dd_file)
                    datasets.create(_dd_file, type="seq")
                else:
                    _dd_file = DatasetDefinition(**ddatr)
            elif ddstmt[ddname]['type'] != "data":
                _dd_file = DatasetDefinition(**ddatr)

            if ddstmt[ddname]['type'] == 'data':
                tfilenamed = tempfile.NamedTemporaryFile(mode='w+b')
                tfilepath = tfilenamed.name
                _sysin_data_block = ddstmt[ddname]['DATA']
                with open(tfilepath, 'w', encoding='cp037') as tfile:
                    for lines in _sysin_data_block.splitlines():
                        lines = lines.ljust(79)
                        tfile.write(" "+lines+"\n")
                _sysin_file = datasets.tmp_name(datasets.hlq(temphlq))
                datasets.create(_sysin_file, type="seq",record_length='80', block_size='0', record_format='FB')
                _sysin_file_name = "//'"+_sysin_file.strip()+"'"
                _dd_file = _sysin_file.strip()
                _del_file_name_list.append(_dd_file)
                subpc = subprocess.run(["cp", tfilepath, _sysin_file_name],
                                       capture_output=False,
                                       check=True)

            _ddlist.append(DDStatement(ddname, _dd_file))
            ddatr = {}

    if opts.pgmauth:
        _response = mvscmd.execute_authorized(pgm=opts.jobpgm, pgm_args=opts.pgmparm, dds=_ddlist)
    else:
        _response = mvscmd.execute(pgm=opts.jobpgm, pgm_args=opts.pgmparm, dds=_ddlist)

    print(_response)
    for delname in _del_file_name_list:
        if _response.rc != 0:
            datasets.read(delname)
        datasets.delete(delname)


def lookup_operational_yaml_vars():

    _optemp_file = tempfile.NamedTemporaryFile(mode='w+b')
    _optemp_file_opened = open(_optemp_file.name, 'w+', encoding='cp037')
    with open(opts.operational_yaml_file, 'r') as opyaml_file:
        for line in opyaml_file.read().splitlines():
            if "{{" and "}}" in line:
                repvars = re.findall(r'\{{.*?\}}', line)
                for repvar in repvars:
                    newlineseg1 = line.split("{{",1)[0]
                    newlineseg2 = line.split("}}",1)[1]
                    repvar = repvar.strip("{{")
                    repvar = repvar.strip("}}")
                    repvar = repvar.strip()
                    getvar = opts.operational_yaml['GLOBALS'][repvar]
                    newline = str(newlineseg1+getvar+newlineseg2)
                    line = newline
            else:
                newline = line
            newline = str(newline+"\n")
            _optemp_file_opened.write(newline)
    _optemp_file_opened.flush()

    # reload yaml since we have made variable substitutions
    opts.operational_yaml = load_yaml_file(_optemp_file.name)


def process_joblist():
    """
      process joblist
    """
    global opts
    for jobname in opts.operational_yaml['JOBS']:
        print(f"Submitting job: {jobname}")
        run_job(jobname)


def main():
    """
      main
    """
    parse_our_args()
    global opts

    opts.operational_yaml = load_yaml_file(opts.operational_yaml_file)

    lookup_operational_yaml_vars()

    process_joblist()


if __name__ == '__main__':
    main()
    sys.exit(opts.max_rc)
