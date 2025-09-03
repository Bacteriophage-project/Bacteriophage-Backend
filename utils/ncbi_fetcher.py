from Bio import Entrez

Entrez.email = "munenejosphat667@gmail.com"
Entrez.api_key = "b44bb23c87259305cefd5a88a714a2ad0008"
Entrez.timeout = 120

def get_genomes_from_bioproject(bioproject_ids):
    """Fetch all genome FASTA URLs and detailed metadata for a list of BioProject IDs."""
    all_genomes = []
    for bioproject_id in bioproject_ids:
        # Get all assembly IDs for this BioProject
        handle = Entrez.esearch(db="assembly", term=f"{bioproject_id}[BioProject]", retmax=1000, api_key=Entrez.api_key)
        record = Entrez.read(handle)
        handle.close()
        assembly_ids = record['IdList']
        if not assembly_ids:
            continue
        # Get assembly summaries
        handle = Entrez.esummary(db="assembly", id=','.join(assembly_ids), api_key=Entrez.api_key)
        summaries = Entrez.read(handle)
        handle.close()
        for summary in summaries['DocumentSummarySet']['DocumentSummary']:
            ftp_path = summary['FtpPath_RefSeq'] or summary['FtpPath_GenBank']
            if not ftp_path:
                continue
            if ftp_path.startswith('ftp://'):
                ftp_path = ftp_path.replace('ftp://', 'https://', 1)
            assembly_name = ftp_path.split('/')[-1]
            fasta_url = f"{ftp_path}/{assembly_name}_genomic.fna.gz"
            
            # Extract detailed metadata
            organism = summary.get('Organism', '')
            organism_parts = organism.split(' (')[0].split() if organism else []
            
            # Parse organism information
            genus = organism_parts[0] if len(organism_parts) > 0 else 'Unknown'
            species = ' '.join(organism_parts[1:3]) if len(organism_parts) > 1 else 'Unknown'
            
            # Extract strain information from various fields
            strain = 'Unknown'
            if 'Strain' in summary:
                strain = summary['Strain']
            elif 'Infraspecies' in summary:
                strain = summary['Infraspecies']
            
            # Get assembly information
            assembly_accession = summary.get('AssemblyAccession', 'Unknown')
            assembly_name_full = summary.get('AssemblyName', 'Unknown')
            assembly_level = summary.get('AssemblyStatus', 'Unknown')
            
            # Get taxonomy information
            taxonomy = summary.get('Taxid', 'Unknown')
            
            # Get submission information
            submitter = summary.get('SubmitterOrganization', 'Unknown')
            submission_date = summary.get('SubmissionDate', 'Unknown')
            
            # Get genome statistics
            contig_count = summary.get('ContigN50', 'Unknown')
            genome_size = summary.get('GenomeSize', 'Unknown')
            
            # Create detailed genome object
            genome_info = {
                'url': fasta_url,
                'genus': genus,
                'species': species,
                'strain': strain,
                'organism': organism,
                'assembly_accession': assembly_accession,
                'assembly_name': assembly_name_full,
                'assembly_level': assembly_level,
                'taxonomy_id': taxonomy,
                'submitter': submitter,
                'submission_date': submission_date,
                'contig_count': contig_count,
                'genome_size': genome_size,
                'bioproject_id': bioproject_id
            }
            
            all_genomes.append(genome_info)
    return all_genomes
