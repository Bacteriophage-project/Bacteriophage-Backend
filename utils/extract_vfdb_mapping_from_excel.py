import pandas as pd
import os

# Path to the VFDB annotation Excel file
VF_ANNOTATION_XLS = os.path.join(os.path.dirname(__file__), 'vfdb_data', 'VFs.xls')
# Output mapping file
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), 'vfdb_data', 'vfdb_gene_category_mapping.csv')

# Read the Excel file (first sheet, header at row 2)
df = pd.read_excel(VF_ANNOTATION_XLS, sheet_name=0, header=1)

# Use 'VF_Name' for gene symbol and 'VFcategory' for category
gene_col = 'VF_Name'
cat_col = 'VFcategory'

if gene_col not in df.columns or cat_col not in df.columns:
    raise ValueError(f"Could not find columns 'VF_Name' or 'VFcategory' in {VF_ANNOTATION_XLS}. Columns found: {df.columns}")

# Extract mapping and drop duplicates
mapping = df[[gene_col, cat_col]].drop_duplicates().dropna()
mapping.columns = ['gene', 'category']
# Only keep rows with non-empty gene and category
mapping = mapping[(mapping['gene'].astype(str).str.strip() != '') & (mapping['category'].astype(str).str.strip() != '')]
# Save to CSV
mapping.to_csv(OUTPUT_CSV, index=False)
print(f"✅ Mapping file saved to: {OUTPUT_CSV}") 
