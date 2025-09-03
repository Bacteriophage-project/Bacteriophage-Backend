df_new = pd.DataFrame(all_records)
    print(f"DataFrame before filtering: {len(df_new)} rows")
    if not df_new.empty and "Accession No" in df_new.columns:
        df_new = df_new[df_new["Accession No"].str.match(r"^(CP|NZ|JA|JAI)", na=False)]
        # Filter to keep valid accession numbers (GCF_, GCA_, NZ_, CP_, JA_, JAI_)
        df_new = df_new[df_new["Accession No"].str.match(r"^(GCF_|GCA_|NZ_|CP_|JA_|JAI_)", na=False)]
    print(f"DataFrame after filtering: {len(df_new)} rows")
    if excel_path and excel_sheet_name:
        try:
