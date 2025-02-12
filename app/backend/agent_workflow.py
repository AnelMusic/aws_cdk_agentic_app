from dotenv import load_dotenv
import os
from huggingface_hub import login
from smolagents import tool, CodeAgent, HfApiModel
from smolagents import LiteLLMModel

load_dotenv() # for local development


# Load environment variables and login to HF
def setup_huggingface():
   """Setup HuggingFace authentication from environment variables"""
   load_dotenv()
   HF_TOKEN = os.getenv('HF_TOKEN')
   if HF_TOKEN is None:
       raise ValueError("HF_TOKEN not found in environment variables. Make sure it's set in your .env file. or SecretManager")
   login(token=HF_TOKEN)

@tool
def get_orthopedic_specialists() -> list[str]:
   """
   Returns detailed information about orthopedic specialists and their subspecialties.
   Returns a list where each entry has format: 'Doctor Name, MD - Subspecialty - Specific expertise'.

   Args:
       None
   """
   print("Retrieving list of all orthopedic specialists with their specialties...")
   try:
       doctors = [
           "Dr. Sarah Johnson, MD - Knee Orthopedics - Specializes in ACL reconstruction and knee replacements",
           "Dr. Michael Chen, MD - Shoulder Orthopedics - Specializes in rotator cuff repair",
           "Dr. Robert Williams, MD - Hip Orthopedics - Specializes in hip replacement surgery",
           "Dr. Emily Rodriguez, MD - Knee Orthopedics - Specializes in arthroscopic knee surgery",
           "Dr. James Smith, MD - Spine Orthopedics - Specializes in spinal fusion"
       ]
       print(f"Successfully retrieved {len(doctors)} doctors")
       return doctors
   except Exception as e:
       print(f"Error retrieving doctors list: {str(e)}")
       raise ValueError(f"Failed to retrieve doctors list. Error: {str(e)}")

@tool
def get_doctor_specialty(doctor_name: str) -> str:
   """
   Returns the specialty information for a specific doctor.
   Returns a string in format: 'Doctor Name - Specialty - Specific expertise'

   Args:
       doctor_name: Full name of the doctor including credentials (e.g., "Dr. Sarah Johnson, MD")
   """
   print(f"Looking up specialty for doctor: {doctor_name}")
   doctor_specialties = {
       "Dr. Sarah Johnson, MD": "Knee Orthopedics - Specializes in ACL reconstruction and knee replacements",
       "Dr. Michael Chen, MD": "Shoulder Orthopedics - Specializes in rotator cuff repair",
       "Dr. Robert Williams, MD": "Hip Orthopedics - Specializes in hip replacement surgery", 
       "Dr. Emily Rodriguez, MD": "Knee Orthopedics - Specializes in arthroscopic knee surgery",
       "Dr. James Smith, MD": "Spine Orthopedics - Specializes in spinal fusion"
   }
   
   if doctor_name in doctor_specialties:
       result = f"{doctor_name} - {doctor_specialties[doctor_name]}"
       print(f"Found specialty information: {result}")
       return result
   
   print(f"No specialty information found for doctor: {doctor_name}")
   return f"No specialty information found for {doctor_name}"

@tool
def get_doctor_availability(doctor_name: str) -> str:
   """
   Returns available time slots for a specific doctor on Mondays in February 2025.
   Returns time slots in CET 24-hour format like "15:30 - 16:00, 17:00 - 18:00"

   Args:
       doctor_name: Full name of the doctor including credentials (e.g., "Dr. Sarah Johnson, MD")
   """
   print(f"Retrieving availability for doctor: {doctor_name}")
   doctor_availability = {
       "Dr. Sarah Johnson, MD": "10:30 - 13:00",
       "Dr. Michael Chen, MD": "14:00 - 14:30",
       "Dr. Robert Williams, MD": "17:00 - 18:00",
       "Dr. Emily Rodriguez, MD": "09:30 - 14:00",
       "Dr. James Smith, MD": "15:00 - 16:30"
   }
   
   if not isinstance(doctor_name, str):
       error_msg = f"Doctor name must be a string, got {type(doctor_name)}"
       print(f"Error: {error_msg}")
       raise TypeError(error_msg)
   
   if doctor_name in doctor_availability:
       result = doctor_availability[doctor_name]
       print(f"Found availability slots: {result}")
       return result
   
   print(f"No availability found for doctor: {doctor_name}")
   return "No availability found"

@tool
def accepts_uninsured_patients(doctor_name: str) -> bool:
   """
   Checks if a specific doctor accepts uninsured patients.
   Returns True if the doctor accepts uninsured patients, False otherwise.

   Args:
       doctor_name: Full name of the doctor including credentials (e.g., "Dr. Sarah Johnson, MD")
   """
   print(f"Checking uninsured patient acceptance for doctor: {doctor_name}")
   doctors_accepting_uninsured = {
       "Dr. Sarah Johnson, MD": True,
       "Dr. Michael Chen, MD": False,
       "Dr. Robert Williams, MD": False,
       "Dr. Emily Rodriguez, MD": True,
       "Dr. James Smith, MD": False
   }
   
   if doctor_name in doctors_accepting_uninsured:
       result = doctors_accepting_uninsured[doctor_name]
       print(f"Doctor {doctor_name} accepts uninsured patients: {result}")
       return result
   
   print(f"No insurance policy information found for doctor: {doctor_name}")
   return False

def setup_agent():
   """Setup and return the CodeAgent with all tools"""
   model = HfApiModel()
   return CodeAgent(
       tools=[
           get_orthopedic_specialists,
           get_doctor_specialty,
           get_doctor_availability,
           accepts_uninsured_patients
       ],
       model=model
   )


def get_agent():
    """Setup and return the CodeAgent with all tools"""
    setup_huggingface()  
    # model = HfApiModel("Qwen/Qwen2.5-Coder-32B-Instruct") # Default model currently down.
    model = LiteLLMModel(model_id="openai/gpt-4o-mini",api_key=os.getenv('OPENAI_API_KEY'))
    return CodeAgent(
        tools=[
            get_orthopedic_specialists,
            get_doctor_specialty,
            get_doctor_availability,
            accepts_uninsured_patients
        ],
        model=model
    )

# Keep the original main function for debugging
def debug_run():
    agent = get_agent()
    instruction = """Find one or more orthopedic specialist (knee doctor) who:
    1. Accepts uninsured patients
    2. Has availability for appointments on Mondays between 8:00 - 12:00 CET
    3. Can schedule a 30 min appointment for February 2025
    4. The final answer should be a complete information a patient can use to make an informed decision regarding 1., 2., 3. If no slots are available inform the patient as well.
    5. Answer in a complete sentence or paragraph in human redable form."""
    output = agent.run(instruction)
    print(output)
    
    
if __name__ == "__main__":
    debug_run()
    


