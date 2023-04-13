"""                                                              
rawjobs sample                                                   
"""                                                              
from tempfile import mkstemp                                     
import sys                                                       
import os                                                        
import subprocess                                                
import argparse                                                  
import yaml                                                      
                                                                 
def parse_args(argv=None):                                       
    """                                                          
    get arguments                                                
    """                                                          
    global opts                                                  
    program_name = os.path.basename(sys.argv[0])                 
    if argv is None:                                             
        argv = sys.argv[1:]                                      
                                                                 
    parser = argparse.ArgumentParser(program_name)               
    parser.add_argument(                                         
                        "-debug",                                
                        "--debug",                               
                        action='store_true',                     
                        help="Turn on Debugging",                
                        required=False                           
                        )                                        
    parser.add_argument(                                         
                       "-jclyaml",                               
                       "--rawjobs_yaml_file",                    
                       help="YAML file with JCL",                
                       required=False                            
                       )                                         
    opts = parser.parse_args(argv)                               
                                                                 
    opts.program_name = program_name                             
                                                                 
    opts.script_dir = os.path.dirname(os.path.abspath(__file__)) 
    if opts.rawjobs_yaml_file is None:                                                         
        _default_rawjobs_yaml_file = "rawjobs.yaml"                                            
        opts.rawjobs_yaml_file = opts.script_dir + "/" + _default_rawjobs_yaml_file            
                                                                                               
                                                                                               
def load_yaml_file(yaml_file):                                                                 
    """                                                                                        
    load yaml file                                                                             
    """                                                                                        
    # Open the yaml file and load the data into defaults                                       
    with open(yaml_file,encoding="cp037") as file:                                             
        _yamldata = yaml.safe_load(file)                                                       
    return _yamldata                                                                           
                                                                                               
                                                                                               
def run_rawjob(rawjobs_yaml, rawjobname):                                                      
    """                                                                                        
    run the jcl                                                                                
    """                                                                                        
                                                                                               
    _jcl_data_block = rawjobs_yaml['RAWJOBS'][rawjobname]['DATA']                              
                                                                                               
    if 'MAXCC' in rawjobs_yaml['RAWJOBS'][rawjobname].keys():                                  
        jcl_maxcc = rawjobs_yaml['RAWJOBS'][rawjobname]['MAXCC']                               
    else:                                                                                      
        jcl_maxcc = 0                                                                          
                                                                                               
    jcl_fd, jcl_path = mkstemp()                                                               
    with os.fdopen(jcl_fd, 'w', encoding='cp037') as jclfile:                                  
        for lines in _jcl_data_block.splitlines():                                             
            lines = lines.ljust(79)                                                            
            jclfile.write(lines+"\n")                                                          
                                                                                               
    runjob = subprocess.run(['submit', jcl_path],capture_output=True, text=True, check=True)   
    jclfile.close()                                                                            
                                                                                               
    jobid = runjob.stdout.split()[1].strip()                                                   
    getoutput = subprocess.run(["pjdd", jobid, '*'],capture_output=True, text=True, check=True)
                                                                                          
     return(rawjobname, getoutput, jcl_maxcc)                                             
                                                                                          
                                                                                          
 def process_output(rawjobname,getoutput,jcl_maxcc):                                      
     """                                                                                  
     process output and find max cc or failures                                           
     """                                                                                  
     job_cc = 0                                                                           
     job_cc_str = ''                                                                      
     halt_jobs = False                                                                    
     job_cc_srcstr = ["COMPLETION CODE", "JOB FAILED", "JCL ERROR", "JOB NOT RUN"]        
                                                                                          
     for joblines in getoutput.stdout.splitlines():                                       
         for srcstr in job_cc_srcstr:                                                     
             if srcstr in joblines:                                                       
                 print(srcstr)                                                            
                 job_cc_str = str(joblines.split()[4:])                                   
                 print(rawjobname + " Completed with condition:           " + job_cc_str) 
         if "STEP WAS EXECUTED - COND CODE" in joblines:                                  
             if int(joblines.split()[-1]) > job_cc:                                       
                 job_cc = int(joblines.split()[-1])                                       
     if job_cc_str == '':                                                                 
         print(rawjobname + " Step Completed with Return code: " + str(job_cc))           
                                                                                          
     if job_cc > jcl_maxcc or job_cc_str != '':                                           
         halt_jobs = True                                                                 
                                                                                          
     return halt_jobs                                                                     
                                                                                          
                                                                                          
 def process_joblist(rawjobs_yaml):                                                       
     """                                                                                  
     process joblist from yaml                                                            
     """                                                                                  
     for rawjobname in rawjobs_yaml['RAWJOBS']:                                           
         rawjobname, getoutput, jcl_maxcc = run_rawjob(rawjobs_yaml, rawjobname)          
         halt_jobs = process_output(rawjobname,getoutput,jcl_maxcc)                       
         if halt_jobs:                                                                    
             print("Job stream halted due to maxcc condition")                            
             break                                         
                                                           
                                                           
 def main():                                               
     """                                                   
     main                                                  
     """                                                   
     parse_args()                                          
     rawjobs_yaml = load_yaml_file(opts.rawjobs_yaml_file) 
     process_joblist(rawjobs_yaml)                         
                                                           
                                                           
 if __name__ == '__main__':                                
     main()                                                
     sys.exit()                                            
