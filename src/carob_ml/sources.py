"""Where the support-routing data comes from, pinned so every run reads the same bytes.

See docs/data/README.md for what each source contains and its license.
"""

BANKING77 = {
    "repo": "mteb/banking77",
    "revision": "18072d2685ea682290f7b8924d94c62acc19c0b2",
    "license": "MIT (dataset card); the original PolyAI release is CC BY 4.0",
}

ARBANKING77 = {
    "repo": "SinaLab/ArBanking77",
    "commit": "2e3a5639e254bc28828ed0af6d3059d64d3b97fc",
    "base_url": "https://raw.githubusercontent.com/SinaLab/ArBanking77/{commit}/data/{file}",
    "license": "MIT, according to the Hugging Face model card (SinaLab/ArBanking77)",
    "train": "Banking77_Arabized_MSA_PAL_train.csv",
    "val": "Banking77_Arabized_MSA_PAL_val.csv",
    "intents": "Banking77_intents.csv",
    # Test sets, one per variety. The train and validation files mix MSA and
    # Palestinian Arabic without saying which row is which.
    "test": {
        "msa": "Banking77_Arabized_MSA_test.csv",
        "pal": "Banking77_Arabized_PAL_test.csv",
        "saudi": "Banking77_Arabized_Saudi_test.csv",
        "moroccan": "Banking77_Arabized_Moroccan_test.csv",
        "tunisian": "Banking77_Arabized_Tunisian_test.csv",
    },
}
