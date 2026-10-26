import os
import re

BRAND_MAPPING = {
    # Backgrounds
    r'bg-slate-950': 'bg-[#111111]',
    r'bg-slate-900': 'bg-[#0F0F72]',
    r'bg-slate-800': 'bg-[#0F0F72]',
    r'bg-slate-700': 'bg-[#2800C8]',
    r'bg-slate-600': 'bg-[#2800C8]',
    r'bg-indigo-600': 'bg-[#2800C8]',
    r'bg-indigo-500': 'bg-[#2800C8]',
    
    # Text
    r'text-slate-100': 'text-[#FFFFFF]',
    r'text-slate-200': 'text-[#F2F0EB]',
    r'text-slate-300': 'text-[#F2F0EB]',
    r'text-slate-400': 'text-[#A6B7FF]',
    r'text-slate-500': 'text-[#A6B7FF]',
    r'text-indigo-400': 'text-[#A6B7FF]',
    r'text-indigo-300': 'text-[#A6B7FF]',
    r'text-white': 'text-[#FFFFFF]',
    r'text-amber-400': 'text-[#F0FA00]',
    r'text-amber-300': 'text-[#F0FA00]',
    r'text-purple-400': 'text-[#A6B7FF]',
    
    # Borders & Rings
    r'border-slate-800': 'border-[#0F0F72]',
    r'border-slate-700': 'border-[#0F0F72]',
    r'border-slate-600': 'border-[#2800C8]',
    r'border-indigo-500': 'border-[#2800C8]',
    r'ring-indigo-400': 'ring-[#A6B7FF]',
    r'ring-indigo-500': 'ring-[#2800C8]',
    
    # Gradients
    r'from-indigo-600': 'from-[#2800C8]',
    r'to-purple-600': 'to-[#0F0F72]',
    r'from-indigo-500': 'from-[#2800C8]',
    r'to-purple-500': 'to-[#0F0F72]',
    r'from-amber-600': 'from-[#F0FA00]',
    r'to-orange-600': 'to-[#F0FA00]',
}

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    for old, new in BRAND_MAPPING.items():
        # Match the word so we don't accidentally replace bg-slate-900 inside bg-slate-9000 (though tailwind doesn't have 9000)
        # We need to handle opacity like bg-slate-900/50.
        # So we use a regex that matches the class name and captures the opacity part if any.
        pattern = r'\b' + old + r'(?P<opacity>/\d+)?\b'
        
        def replacer(match):
            opacity = match.group('opacity') or ''
            return new + opacity
            
        content = re.sub(pattern, replacer, content)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

src_dir = r"c:\Users\hossam\Desktop\crewai-bpo-challenge\frontend\src"

# Process App.tsx
process_file(os.path.join(src_dir, "App.tsx"))

# Process components
comp_dir = os.path.join(src_dir, "components")
for filename in os.listdir(comp_dir):
    if filename.endswith(".tsx"):
        process_file(os.path.join(comp_dir, filename))

print("Updates completed.")
