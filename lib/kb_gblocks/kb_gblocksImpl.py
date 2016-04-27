#BEGIN_HEADER
import os
import sys
import shutil
import hashlib
import subprocess
import requests
import re
import traceback
import uuid
from datetime import datetime
from pprint import pprint, pformat
import numpy as np
import gzip

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.Alphabet import generic_protein
from biokbase.workspace.client import Workspace as workspaceService
from requests_toolbelt import MultipartEncoder  # added
from biokbase.AbstractHandle.Client import AbstractHandle as HandleService  # added

# silence whining
import requests
requests.packages.urllib3.disable_warnings()
#END_HEADER


class kb_gblocks:
    '''
    Module Name:
    kb_gblocks

    Module Description:
    ** A KBase module: gblocks
**
** This module runs Gblocks trim Multiple Sequence Alignments (MSAs) to remove hypervariable (gappy) regions using Gblocks
**
    '''

    ######## WARNING FOR GEVENT USERS #######
    # Since asynchronous IO can lead to methods - even the same method -
    # interrupting each other, you must be *very* careful when using global
    # state. A method could easily clobber the state set by another while
    # the latter method is running.
    #########################################
    #BEGIN_CLASS_HEADER
    workspaceURL = None
    shockURL = None
    handleURL = None

    GBLOCKS_bin = '/kb/module/Gblocks'

    # target is a list for collecting log messages
    def log(self, target, message):
        # we should do something better here...
        if target is not None:
            target.append(message)
        print(message)
        sys.stdout.flush()

    def get_single_end_read_library(self, ws_data, ws_info, forward):
        pass

    def get_feature_set_seqs(self, ws_data, ws_info):
        pass

    def get_genome_feature_seqs(self, ws_data, ws_info):
        pass

    def get_genome_set_feature_seqs(self, ws_data, ws_info):
        pass

    # config contains contents of config file in a hash or None if it couldn't
    # be found
    def __init__(self, config):
        #BEGIN_CONSTRUCTOR
        self.workspaceURL = config['workspace-url']
        self.shockURL = config['shock-url']
        self.handleURL = config['handle-service-url']
        self.scratch = os.path.abspath(config['scratch'])
        # HACK!! temporary hack for issue where megahit fails on mac because of silent named pipe error
        #self.host_scratch = self.scratch
        self.scratch = os.path.join('/kb','module','local_scratch')
        # end hack
        if not os.path.exists(self.scratch):
            os.makedirs(self.scratch)

        #END_CONSTRUCTOR
        pass


    # Helper script borrowed from the transform service, logger removed
    #
    def upload_file_to_shock(self,
                             console,  # DEBUG
                             shock_service_url = None,
                             filePath = None,
                             ssl_verify = True,
                             token = None):
        """
        Use HTTP multi-part POST to save a file to a SHOCK instance.
        """
        self.log(console,"UPLOADING FILE "+filePath+" TO SHOCK")

        if token is None:
            raise Exception("Authentication token required!")

        #build the header
        header = dict()
        header["Authorization"] = "Oauth {0}".format(token)
        if filePath is None:
            raise Exception("No file given for upload to SHOCK!")

        dataFile = open(os.path.abspath(filePath), 'rb')
        m = MultipartEncoder(fields={'upload': (os.path.split(filePath)[-1], dataFile)})
        header['Content-Type'] = m.content_type

        #logger.info("Sending {0} to {1}".format(filePath,shock_service_url))
        try:
            response = requests.post(shock_service_url + "/node", headers=header, data=m, allow_redirects=True, verify=ssl_verify)
            dataFile.close()
        except:
            dataFile.close()
            raise
        if not response.ok:
            response.raise_for_status()
        result = response.json()
        if result['error']:
            raise Exception(result['error'][0])
        else:
            return result["data"]


    def upload_SingleEndLibrary_to_shock_and_ws (self,
                                                 ctx,
                                                 console,  # DEBUG
                                                 workspace_name,
                                                 obj_name,
                                                 file_path,
                                                 provenance,
                                                 sequencing_tech):

        self.log(console,'UPLOADING FILE '+file_path+' TO '+workspace_name+'/'+obj_name)

        # 1) upload files to shock
        token = ctx['token']
        forward_shock_file = self.upload_file_to_shock(
            console,  # DEBUG
            shock_service_url = self.shockURL,
            filePath = file_path,
            token = token
            )
        #pprint(forward_shock_file)
        self.log(console,'SHOCK UPLOAD DONE')

        # 2) create handle
        self.log(console,'GETTING HANDLE')
        hs = HandleService(url=self.handleURL, token=token)
        forward_handle = hs.persist_handle({
                                        'id' : forward_shock_file['id'], 
                                        'type' : 'shock',
                                        'url' : self.shockURL,
                                        'file_name': forward_shock_file['file']['name'],
                                        'remote_md5': forward_shock_file['file']['checksum']['md5']})

        
        # 3) save to WS
        self.log(console,'SAVING TO WORKSPACE')
        single_end_library = {
            'lib': {
                'file': {
                    'hid':forward_handle,
                    'file_name': forward_shock_file['file']['name'],
                    'id': forward_shock_file['id'],
                    'url': self.shockURL,
                    'type':'shock',
                    'remote_md5':forward_shock_file['file']['checksum']['md5']
                },
                'encoding':'UTF8',
                'type':'fasta',
                'size':forward_shock_file['file']['size']
            },
            'sequencing_tech':sequencing_tech
        }
        self.log(console,'GETTING WORKSPACE SERVICE OBJECT')
        ws = workspaceService(self.workspaceURL, token=ctx['token'])
        self.log(console,'SAVE OPERATION...')
        new_obj_info = ws.save_objects({
                        'workspace':workspace_name,
                        'objects':[
                            {
                                'type':'KBaseFile.SingleEndLibrary',
                                'data':single_end_library,
                                'name':obj_name,
                                'meta':{},
                                'provenance':provenance
                            }]
                        })[0]
        self.log(console,'SAVED TO WORKSPACE')

        return new_obj_info[0]

    #END_CLASS_HEADER

    # config contains contents of config file in a hash or None if it couldn't
    # be found
    def __init__(self, config):
        #BEGIN_CONSTRUCTOR
        self.workspaceURL = config['workspace-url']
        self.shockURL = config['shock-url']
        self.handleURL = config['handle-service-url']
        self.scratch = os.path.abspath(config['scratch'])
        # HACK!! temporary hack for issue where megahit fails on mac because of silent named pipe error
        #self.host_scratch = self.scratch
        self.scratch = os.path.join('/kb','module','local_scratch')
        # end hack
        if not os.path.exists(self.scratch):
            os.makedirs(self.scratch)

        #END_CONSTRUCTOR
        pass

    def run_Gblocks(self, ctx, params):
        # ctx is the context object
        # return variables are: returnVal
        #BEGIN run_Gblocks
        console = []
        invalid_msgs = []
        self.log(console,'Running run_Gblocks with params=')
        self.log(console, "\n"+pformat(params))
        report = ''
#        report = 'Running run_Gblocks with params='
#        report += "\n"+pformat(params)


        #### do some basic checks
        #
        if 'workspace_name' not in params:
            raise ValueError('workspace_name parameter is required')
        if 'input_name' not in params:
            raise ValueError('input_name parameter is required')
        if 'output_name' not in params:
            raise ValueError('output_name parameter is required')


        #### Get the input_name MSA object
        ##
        try:
            ws = workspaceService(self.workspaceURL, token=ctx['token'])
            objects = ws.get_objects([{'ref': params['workspace_name']+'/'+params['input_name']}])
            data = objects[0]['data']
            info = objects[0]['info']
            input_type_name = info[2].split('.')[1].split('-')[0]

        except Exception as e:
            raise ValueError('Unable to fetch input_name object from workspace: ' + str(e))
            #to get the full stack trace: traceback.format_exc()

        if input_type_name == 'MSA':
            MSA_in = data
            row_order = []
            default_row_labels = dict()
            if 'row_order' in MSA_in.keys():
                row_order = MSA_in['row_order']
            else:
                row_order = sorted(MSA_in['alignment'].keys())

            if 'default_row_labels' in MSA_in.keys():
                default_row_labels = MSA_in['default_row_labels']
            else:
                for row_id in row_order:
                    default_row_labels[row_id] = row_id
            if len(row_order) < 2:
                self.log(invalid_msgs,"must have multiple records in MSA: "+params['input_name'])

            # export features to FASTA file
            input_MSA_file_path = os.path.join(self.scratch, params['input_name']+".fasta")
            self.log(console, 'writing fasta file: '+input_MSA_file_path)
            records = []
            for row_id in row_order:
                #self.log(console,"row_id: '"+row_id+"'")  # DEBUG
                #self.log(console,"alignment: '"+MSA_in['alignment'][row_id]+"'")  # DEBUG
            # using SeqIO makes multiline sequences.  (Gblocks doesn't care, but FastTree doesn't like multiline, and I don't care enough to change code)
                #record = SeqRecord(Seq(MSA_in['alignment'][row_id]), id=row_id, description=default_row_labels[row_id])
                #records.append(record)
            #SeqIO.write(records, input_MSA_file_path, "fasta")
                records.extend(['>'+row_id,
                                MSA_in['alignment'][row_id]
                               ])
            with open(input_MSA_file_path,'w',0) as input_MSA_file_handle:
                input_MSA_file_handle.write("\n".join(records)+"\n")


            # Determine whether nuc or protein sequences
            #
            NUC_MSA_pattern = re.compile("^[\.\-_ACGTUXNRYSWKMBDHVacgtuxnryswkmbdhv \t\n]+$")
            all_seqs_nuc = True
            for row_id in row_order:
                #self.log(console, row_id+": '"+MSA_in['alignment'][row_id]+"'")
                if NUC_MSA_pattern.match(MSA_in['alignment'][row_id]) == None:
                    all_seqs_nuc = False
                    break

        # Missing proper input_type
        #
        else:
            raise ValueError('Cannot yet handle input_name type of: '+type_name)


        # DEBUG: check the MSA file contents
#        with open(input_MSA_file_path, 'r', 0) as input_MSA_file_handle:
#            for line in input_MSA_file_handle:
#                #self.log(console,"MSA_LINE: '"+line+"'")  # too big for console
#                self.log(invalid_msgs,"MSA_LINE: '"+line+"'")


        # validate input data
        #
        N_seqs = 0
        L_first_seq = 0
        with open(input_MSA_file_path, 'r', 0) as input_MSA_file_handle:
            for line in input_MSA_file_handle:
                if line.startswith('>'):
                    N_seqs += 1
                    if L_first_seq == 0:
                        for c in line:
                            if c != '-' and c != "\n":
                                L_first_seq += 1
        # min_seqs_for_conserved
        if params['min_seqs_for_conserved'] < int(0.5*N_seqs)+1:
            self.log(invalid_msgs,"Min Seqs for Conserved Pos ("+str(params['min_seqs_for_conserved'])+") must be >= N/2+1 (N="+str(N_seqs)+", N/2+1="+str(int(0.5*N_seqs)+1)+")\n")
        if params['min_seqs_for_conserved'] > params['min_seqs_for_flank']:
            self.log(invalid_msgs,"Min Seqs for Conserved Pos ("+str(params['min_seqs_for_conserved'])+") must be <= Min Seqs for Flank Pos ("+str(params['min_seqs_for_flank'])+")\n")

        # min_seqs_for_flank
        if params['min_seqs_for_flank'] > N_seq:
            self.log(invalid_msgs,"Min Seqs for Flank Pos ("+str(params['min_seqs_for_flank'])+") must be <= N (N="+str(N_seqs)+")\n")

        # max_pos_contig_nonconserved
        if params['max_pos_contig_nonconserved'] < 0:
            self.log(invalid_msgs,"Max Num Non-Conserved Pos ("+str(params['max_pos_contig_nonconserved'])+") must be >= 0"+"\n")
        if params['max_pos_contig_nonconserved'] > L_first_seq or params['max_pos_contig_nonconserved'] >= 32000:
            self.log(invalid_msgs,"Max Num Non-Conserved Pos ("+str(params['max_pos_contig_nonconserved'])+") must be <= L first seq ("+str(L_first_seq)+") and < 32000\n")

        # min_block_len
        if params['min_block_len'] < 2:
            self.log(invalid_msgs,"Min Block Len ("+str(params['min_block_len'])+") must be >= 2"+"\n")
        if params['min_block_len'] > L_first_seq or params['max_block_len'] >= 32000:
            self.log(invalid_msgs,"Min Block Len ("+str(params['min_block_len'])+") must be <= L first seq ("+str(L_first_seq)+") and < 32000\n")

        # trim_level
        if params['trim_level'] < 0 or params['trim_level'] > 2:
            self.log(invalid_msgs,"Trim Level ("+str(params['trim_level'])+") must be >= 0 and <= 2"+"\n")


        if len(invalid_msgs) > 0:

            # load the method provenance from the context object
            self.log(console,"SETTING PROVENANCE")  # DEBUG
            provenance = [{}]
            if 'provenance' in ctx:
                provenance = ctx['provenance']
            # add additional info to provenance here, in this case the input data object reference
            provenance[0]['input_ws_objects'] = []
            provenance[0]['input_ws_objects'].append(params['workspace_name']+'/'+params['input_name'])
            if 'intree' in params and params['intree'] != None:
                provenance[0]['input_ws_objects'].append(params['workspace_name']+'/'+params['intree'])
            provenance[0]['service'] = 'kb_gblocks'
            provenance[0]['method'] = 'run_Gblocks'

            # report
            report += "FAILURE\n\n"+"\n".join(invalid_msgs)+"\n"
            reportObj = {
                'objects_created':[],
                'text_message':report
                }

            reportName = 'gblocks_report_'+str(hex(uuid.getnode()))
            report_obj_info = ws.save_objects({
#                'id':info[6],
                'workspace':params['workspace_name'],
                'objects':[
                    {
                        'type':'KBaseReport.Report',
                        'data':reportObj,
                        'name':reportName,
                        'meta':{},
                        'hidden':1,
                        'provenance':provenance
                    }
                ]
            })[0]


            self.log(console,"BUILDING RETURN OBJECT")
            returnVal = { 'report_name': reportName,
                          'report_ref': str(report_obj_info[6]) + '/' + str(report_obj_info[0]) + '/' + str(report_obj_info[4]),
                          'output_ref': None
                          }
            self.log(console,"run_Gblocks DONE")
            return [returnVal]


        ### Construct the command
        #
        #  e.g.
        #  for "0.5" gaps: cat "o\n<MSA_file>\nb\n5\ng\nm\nq\n" | Gblocks
        #  for "all" gaps: cat "o\n<MSA_file>\nb\n5\n5\ng\nm\nq\n" | Gblocks
        #
        gblocks_cmd = [self.GBLOCKS_bin]

        # check for necessary files
        if not os.path.isfile(self.GBLOCKS_bin):
            raise ValueError("no such file '"+self.GBLOCKS_bin+"'")
        if not os.path.isfile(input_MSA_file_path):
            raise ValueError("no such file '"+input_MSA_file_path+"'")
        if not os.path.getsize(input_MSA_file_path) > 0:
            raise ValueError("empty file '"+input_MSA_file_path+"'")

        # DEBUG
#        with open(input_MSA_file_path,'r',0) as input_MSA_file_handle:
#            for line in input_MSA_file_handle:
#                #self.log(console,"MSA LINE: '"+line+"'")  # too big for console
#                self.log(invalid_msgs,"MSA LINE: '"+line+"'")


        # set the output path
        timestamp = int((datetime.utcnow() - datetime.utcfromtimestamp(0)).total_seconds()*1000)
        output_dir = os.path.join(self.scratch,'output.'+str(timestamp))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Gblocks names output blocks MSA by appending "-gb" to input file
        output_MSA_file_path = os.path.join(output_dir, params['input_name']+'-gb');

        # Gblocks is interactive and only accepts args from pipe input
        #if 'arg' in params and params['arg'] != None and params['arg'] != 0:
        #    fasttree_cmd.append('-arg')
        #    fasttree_cmd.append(val)


        # Run GBLOCKS, capture output as it happens
        #
        self.log(console, 'RUNNING GBLOCKS:')
        self.log(console, '    '+' '.join(gblocks_cmd))
#        report += "\n"+'running GBLOCKS:'+"\n"
#        report += '    '+' '.join(gblocks_cmd)+"\n"

        # FastTree requires shell=True in order to see input data
        env = os.environ.copy()
        p = subprocess.Popen(fasttree_cmd, \
        #joined_fasttree_cmd = ' '.join(fasttree_cmd)  # redirect out doesn't work with subprocess unless you join command first
        p = subprocess.Popen(gblocks_cmd, \
                             cwd = self.scratch, \
                             stdin = subprocess.PIPE, \
                             stdout = subprocess.PIPE, \
                             stderr = subprocess.PIPE, \
                             shell = True, \
                             env = env)
#                             executable = '/bin/bash' )

        
        # write commands to process
        #
        #  for "0.5" gaps: cat "o\n<MSA_file>\nb\n5\ng\nm\nq\n" | Gblocks
        #  for "all" gaps: cat "o\n<MSA_file>\nb\n5\n5\ng\nm\nq\n" | Gblocks

        p.stdin.write("o"+"\n")  # open MSA file
        p.stdin.write(input_MSA_file_path+"\n")

        if 'trim_level' in params and params['trim_level'] != None and params['trim_level'] != 0:
             p.stdin.write("b"+"\n")
             if params['trim_level'] >= 1:
                  p.stdin.write("5"+"\n")  # set to "half"
                  if params['trim_level'] == 2:
                       p.stdin.write("5"+"\n")  # set to "all"
             p.stdin.write("m"+"\n")

        # flank must precede conserved because it acts us upper bound for acceptable conserved values
        if 'min_seqs_for_flank' in params and params['min_seqs_for_flank'] != None and params['min_seqs_for_flank'] != 0:
             p.stdin.write("b"+"\n")
             p.stdin.write("2"+"\n")
             p.stdin.write(str(params['min_seqs_for_flank'])+"\n")
             p.stdin.write("m"+"\n")

        if 'min_seqs_for_conserved' in params and params['min_seqs_for_conserved'] != None and params['min_seqs_for_conserved'] != 0:
             p.stdin.write("b"+"\n")
             p.stdin.write("1"+"\n")
             p.stdin.write(str(params['min_seqs_for_conserved'])+"\n")
             p.stdin.write("m"+"\n")

        if 'max_pos_contig_nonconserved' in params and params['max_pos_contig_nonconserved'] != None and params['max_pos_contig_nonconserved'] > -1:
             p.stdin.write("b"+"\n")
             p.stdin.write("3"+"\n")
             p.stdin.write(str(params['max_pos_contig_nonconserved'])+"\n")
             p.stdin.write("m"+"\n")

        if 'min_block_len' in params and params['min_block_len'] != None and params['min_block_len'] != 0:
             p.stdin.write("b"+"\n")
             p.stdin.write("4"+"\n")
             p.stdin.write(str(params['min_block_len'])+"\n")
             p.stdin.write("m"+"\n")
        
        p.stdin.write("g"+"\n")  # get blocks
        p.stdin.write("q"+"\n")  # quit
        p.stdin.close()
        p.wait()


        # Read output
        #
        while True:
            line = p.stdout.readline()
            #line = p.stderr.readline()
            if not line: break
            self.log(console, line.replace('\n', ''))

        p.stdout.close()
        #p.stderr.close()
        p.wait()
        self.log(console, 'return code: ' + str(p.returncode))
        if p.returncode != 0:
            raise ValueError('Error running GBLOCKS, return code: '+str(p.returncode) + 
                '\n\n'+ '\n'.join(console))

        # Check that GBLOCKS produced output
        #
        if not os.path.isfile(output_MSA_file_path):
            raise ValueError("failed to create GBLOCKS output: "+output_MSA_file_path)
        elif not os.path.getsize(output_MSA_file_path) > 0:
            raise ValueError("created empty file for GBLOCKS output: "+output_MSA_file_path)


        # reformat output to MSA and check that output not empty (often happens when param combinations don't produce viable blocks
        #
# HERE

        # load the method provenance from the context object
        #
        self.log(console,"SETTING PROVENANCE")  # DEBUG
        provenance = [{}]
        if 'provenance' in ctx:
            provenance = ctx['provenance']
        # add additional info to provenance here, in this case the input data object reference
        provenance[0]['input_ws_objects'] = []
        provenance[0]['input_ws_objects'].append(params['workspace_name']+'/'+params['input_name'])
        provenance[0]['service'] = 'kb_gblocks'
        provenance[0]['method'] = 'run_Gblocks'


        # Upload results
        #
        if len(invalid_msgs) == 0:
            self.log(console,"UPLOADING RESULTS")  # DEBUG

            tree_name = params['output_name']
            tree_description = params['desc']
            tree_type = 'GeneTree'
            if 'species_tree_flag' in params and params['species_tree_flag'] != None and params['species_tree_flag'] != 0:
                tree_type = 'SpeciesTree'

            with open(output_newick_file_path,'r',0) as output_newick_file_handle:
                output_newick_buf = output_newick_file_handle.read()
            output_newick_buf = output_newick_buf.rstrip()
            self.log(console,"\nNEWICK:\n"+output_newick_buf+"\n")
        
            # Extract info from MSA
            #
            tree_attributes = None
            default_node_labels = None
            ws_refs = None
            kb_refs = None
            leaf_list = None
            if default_row_labels != None:
                default_node_labels = dict()
                leaf_list = []
                for row_id in default_row_labels.keys():
                    default_node_labels[row_id] = default_row_labels[row_id]
                    leaf_list.append(row_id)

            if 'ws_refs' in MSA_in.keys() and MSA_in['ws_refs'] != None:
                ws_refs = MSA_in['ws_refs']
            if 'kb_refs' in MSA_in.keys() and MSA_in['kb_refs'] != None:
                kb_refs = MSA_in['kb_refs']

            # Build output_Tree structure
            #
            output_Tree = {
                      'name': tree_name,
                      'description': tree_description,
                      'type': tree_type,
                      'tree': output_newick_buf
                     }
            if tree_attributes != None:
                output_Tree['tree_attributes'] = tree_attributes
            if default_node_labels != None:
                output_Tree['default_node_labels'] = default_node_labels
            if ws_refs != None:
                output_Tree['ws_refs'] = ws_refs 
            if kb_refs != None:
                output_Tree['kb_refs'] = kb_refs
            if leaf_list != None:
                output_Tree['leaf_list'] = leaf_list 

            # Store output_Tree
            #
            new_obj_info = ws.save_objects({
                            'workspace': params['workspace_name'],
                            'objects':[{
                                    'type': 'KBaseTrees.Tree',
                                    'data': output_Tree,
                                    'name': params['output_name'],
                                    'meta': {},
                                    'provenance': provenance
                                }]
                        })[0]


        # build output report object
        #
        self.log(console,"BUILDING REPORT")  # DEBUG

        if len(invalid_msgs) == 0:
            #self.log(console,"sequences in many set: "+str(seq_total))
            #self.log(console,"sequences in hit set:  "+str(hit_total))
            #report += 'sequences in many set: '+str(seq_total)+"\n"
            #report += 'sequences in hit set:  '+str(hit_total)+"\n"
            report += output_newick_buf+"\n"
            reportObj = {
                'objects_created':[{'ref':params['workspace_name']+'/'+params['output_name'], 'description':'Gblocks MSA'}],
                'text_message':report
                }
        else:
            report += "FAILURE\n\n"+"\n".join(invalid_msgs)+"\n"
            reportObj = {
                'objects_created':[],
                'text_message':report
                }

        reportName = 'gblocks_report_'+str(hex(uuid.getnode()))
        report_obj_info = ws.save_objects({
#                'id':info[6],
                'workspace':params['workspace_name'],
                'objects':[
                    {
                        'type':'KBaseReport.Report',
                        'data':reportObj,
                        'name':reportName,
                        'meta':{},
                        'hidden':1,
                        'provenance':provenance
                    }
                ]
            })[0]


        self.log(console,"BUILDING RETURN OBJECT")
        returnVal = { 'report_name': reportName,
                      'report_ref': str(report_obj_info[6]) + '/' + str(report_obj_info[0]) + '/' + str(report_obj_info[4]),
                      'output_ref': str(new_obj_info[6]) + '/' + str(new_obj_info[0]) + '/' + str(new_obj_info[4])
                      }
        self.log(console,"run_Gblocks DONE")
        #END run_Gblocks

        # At some point might do deeper type checking...
        if not isinstance(returnVal, dict):
            raise ValueError('Method run_Gblocks return value ' +
                             'returnVal is not type dict as required.')
        # return the results
        return [returnVal]