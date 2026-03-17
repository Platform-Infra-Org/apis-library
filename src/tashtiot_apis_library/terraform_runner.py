import subprocess
from subprocess import Popen
import tempfile
import logger
import os
import re
import time
import json
import shutil
import psutil
from pydantic import BaseModel
from typing import Tuple, Union, Optional
from schemas import TerraformOperationResponse, OperationResponse
from .status_code_mappings import status_code_mapping



modules_dir = "terraform_modules/linux-virtual-machine"

def _run_command(command: str, asynchronous: bool = False) -> Union[Tuple[TerraformOperationResponse, Popen], OperationResponse]:
        
    try:
        if asynchronous:
            
            # For long-running commands, run asynchronously

            logger.info(f"Running command asynchronously: {command}")
            print(f"Running command asynchronously: {command}")
            process = subprocess.Popen(
            command, cwd=modules_dir,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True
            )
            print(f"Returning TerraformOperationResponse with process_id {process.pid}, and process object {process}")
            return TerraformOperationResponse(
                status="started",
                status_code=202,
                stdout=f'Started asynchronous- "{command}". Check the logs for progress.',
                process_id=process.pid
            ), process
            
        else:
            
            # For short-running commands, run synchronously
            
            status = "successful"
            logger.info(f"Running synchronously command: {command}")
            print(f"Running synchronously command: {command}")
            
            process = subprocess.run(
                command, cwd=modules_dir,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                check=True, shell=True, timeout=300
            )
            print(f"Command {command} completed with exit code {process.returncode}")
            if process.returncode != 0:
                
                logger.error(f"Error: {process.stderr}")
                print(f"Command failed with exit code {process.returncode}")
                raise Exception(f"Command failed with exit code {process.stderr.strip()}")
                status = "failed"
                
            return OperationResponse(
                status="successful",
                status_code=status_code_mapping[status],
                stdout=process.stdout.strip()
            )
    except Exception as e:
        print(f"Exception: {str(e)}")
        status="failed"
        return OperationResponse(
            status=status,
            stdout=str(e),
            status_code=status_code_mapping[status]
        )       

def get_process_status(process_id: int) -> TerraformOperationResponse:
    status_string = ""
    process = get_process_by_id(process_id)
    try:
        # Check if the process is still running
        pid_finished, status = os.waitpid(process.pid, os.WNOHANG)
        if pid_finished == 0: # Process is still running
            status_string = "running"
        exit_code = os.WEXITSTATUS(status)
        
        if exit_code == 0:
            status_string = "successful"
        else:
            status_string = "failed"
            
        return TerraformOperationResponse(
            status=status_string,
            status_code=status_code_mapping[status_string],
            stdout=process.stdout.strip(),
            process_id=process.pid
        )
        
    except Exception as e:
        print(f"Failed polling Terraform command: {str(e)}")
        
def get_process_by_id(process_id: int) -> Optional[Popen]:
    try:
        process = psutil.Process(process_id)
        return process
    
    except psutil.NoSuchProcess:
        return None
          

def init(resource_type: str, resource: BaseModel) -> TerraformOperationResponse:

    # Generate the backend.tf with a unique state path
    backend_file = _generate_backend_config(resource_type, resource)

    # Initialize Terraform with the generated backend.tf file
    command = f"terraform init -backend-config path={backend_file}"
    return _run_command(command)

def plan(var_file: str = None) -> Union[Tuple[TerraformOperationResponse, Popen], OperationResponse]:
    
    command = "terraform plan"
    if var_file:
        command += f" -var-file={var_file}"
    response, process = _run_command(command, asynchronous=True)
    
    return response, process
    

def apply(var_file: str = None, auto_approve: bool = True) -> Union[Tuple[TerraformOperationResponse, Popen], OperationResponse]:
    
    command = "terraform apply"
    if var_file:
        command += f" -var-file={var_file}"
    if auto_approve:
        command += " -auto-approve"
    response, process = _run_command(command, asynchronous=True)
    
    return response, process

def destory(var_file: str = None, auto_approve: bool = True) -> Union[Tuple[TerraformOperationResponse, Popen], OperationResponse]:
    
    command = "terraform destroy"
    if var_file:
        command += f" -var-file={var_file}"
    if auto_approve:
        command += " -auto-approve"
    response, process = _run_command(command, asynchronous=True)
    
    return response, process

def _generate_backend_config(resource_type: str, resource: BaseModel):

    # Generate a unique path for the statefile in the S3 bucket
    state_key = f"{resource_type}/{resource.tags.project}/{resource.name}@{resource.network}/terraform.tfstate"

    # Load the backend.tf template
    print("trying to open backend.tf")
    with open(f"/workspace/backend.tf", "r") as f:
        backend_template = f.read()
    print("backend.tf opened")
    

    print("trying to replace __STATE_PATH__ with state_key")
    # Replace the placeholder with the generated state path
    backend_config = backend_template.replace("__STATE_PATH__", state_key)
    print("backend.tf replaced")

    print("trying to write backend.tf to temp file")
    # Write the backend config to a temporary file and return the path
    temp_backend_file = f"/tmp/backend_{resource_type}_{resource.name}.tf"
    with open(temp_backend_file, "w") as f:
        f.write(backend_config)
    print("backend.tf written to temp file")

    return str(temp_backend_file)

def generate_vars_file(resource_type: str, resource: BaseModel):

    # Setup var_file
    var_file_path = f"/tmp/terraform_vars_{resource_type}_{resource.name}.tfvars.json"
    with open(var_file_path, "w") as f:
        json.dump(resource.dict(), f)
    
    return str(var_file_path)

def inject_vault_providers():
    
    # Setup Terraform user and password from secret env variables
    terraform_vault_user = os.environ["TERRAFORM_VAULT_USERNAME"]
    terraform_vault_pass = os.environ["TERRAFORM_VAULT_PASSWORD"]
    
    # Setup vault provider files, source and destination
    source_file = '/workspace/terraform-vault-provider.tf'
    destination_directory = '/app/terraform_modules/linux-virtual-machine/'
    destination_file = f'{destination_directory}/terraform-vault-provider.tf'
    
    shutil.copy(source_file, destination_file)
    
    print(f"File {source_file} has been successfully copied to {destination_directory}")

    
    # Load the vault provider file and inject variables
    print(f"trying to open {destination_file} for read")
    with open(destination_file, "r") as f:
        vault_provider_file_content = f.read()
    print(f"{destination_file} opened for read")
    
    vault_provider_file_content = vault_provider_file_content.replace('TERRAFORM_VAULT_USERNAME', terraform_vault_user)
    vault_provider_file_content = vault_provider_file_content.replace('TERRAFORM_VAULT_PASSWORD', terraform_vault_pass)
    
    print(f"trying to open {destination_file} for write")
    with open(destination_file, "w") as f:
        f.write(vault_provider_file_content)
    print(f"{destination_file} opened for write")
    
    print(f"Placeholders in {destination_file} have been successfully replaced")  
        

def remove_vault_provider():
    
    providers_file_path = f"/app/terraform_modules/linux-virtual-machine/providers.tf"

    with open(providers_file_path, 'r+') as f:
        contents = f.read()
        f.seek(0)
        f.write(re.sub(r'provider "vault" {[^}]+}', '', contents))
        f.truncate()
    
