import re
import csv
import os

def extract_vf_name_mapping(long_description_line, output_dir=None):
    columns = [col.strip() for col in long_description_line.strip().split("\t")]
    mapping = []
    for col in columns[1:]:  # Skip "Gene"
        match = re.match(r"\(([^)]+)\)\s*(.+)", col)
        if match:
            vf_name = match.group(1)
            description = match.group(2)
        else:
            vf_name = col.strip().split()[0]
            description = col.strip()
        mapping.append((vf_name, description))
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "vfdb_data")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "vf_name_description_mapping.csv")
    with open(output_file, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["VF_Name", "VF_Description"])
        writer.writerows(mapping)
    print(f"✅ Mapping file saved to: {output_file}")
    return output_file

if __name__ == "__main__":
    # Example usage: paste your long header line here
    long_description_line = "Gene\t(csuA) Csu pilus subunit CsuA\t(pgaA) poly-beta-1,6 N-acetyl-D-glucosamine export porin PgaA"
    extract_vf_name_mapping(long_description_line) 