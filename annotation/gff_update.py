#!/usr/env/bin python

import argparse
from BCBio import GFF
from sys import stderr

def get_opt():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", help = "output file name, default is output.gff3", default = "output.gff3")
    parser.add_argument("old_gff", help=" generated by MAKER or its like")
    parser.add_argument("new_gff", help="Apollo export gff")

    return parser.parse_args()

# read the gff record
def gff_reader(gff_file):
    in_handle = open(gff_file, "r")

    #TODO: check the gff

    records = list(GFF.parse(in_handle))
    # sort the gff list by start position
    for rec in records:
        #rec.seq = ""
        features = rec.features
        rec.features = sorted(features, key=lambda t:t.location.nofuzzy_start)

    in_handle.close()

    return records

# write the gff record
def gff_writer(records, out_file):
    out_handle = open(out_file, "w")
    GFF.write(records, out_handle)
    out_handle.close()

# create the dictionary to store the feature
# for quick modification
def get_model_dict(records):
    model_dict = {}
    for rec in records:
        for feature in rec.features:
            model_dict[feature.id] = feature
    return model_dict

# add new gene to existed models
def add_gene_model(seqfeature, orig_models, idx):
    from bisect import bisect_left
    # format the gene model
    gene_name = seqfeature.qualifiers.get('description')[0]
    format_gene_model([seqfeature], gene_name, {} )
    
    # find the insert position
    position = [ f.location.nofuzzy_start for f in orig_models[idx].features]

    insert_site = bisect_left(position, seqfeature.location.nofuzzy_start)

    # logging
    print("add gene: " + gene_name,file=stderr)
    #print(seqfeature)

    orig_models[idx].features.insert(insert_site, seqfeature)


# rule
# - mRNA: gene_name.{number}
# - other: gene_name.{other}.{number}
# recursive way to change seqfeature
def format_gene_model(subfeature, ID, count):
    # recursive stop rule
    if not subfeature:
        return None

    for sub in subfeature:
        if sub.type == "gene":
            sub.qualifiers['Name'] = ID
            sub.qualifiers['ID'] = ID
            sub.qualifiers['source'] = "apollo"
            format_gene_model(sub.sub_features, sub.qualifiers['ID'],count)
        elif sub.type == "mRNA":
            count["mRNA"] = count.get("mRNA",0) + 1
            name = ID + "." + str(count['mRNA'])
            sub.qualifiers['Name'] = name
            sub.qualifiers['ID'] = name
            sub.qualifiers['Parent'] = ID
            sub.qualifiers['source'] = "apollo"
            format_gene_model(sub.sub_features, sub.qualifiers['ID'], count)
        else :
            feature_type = sub.type 
            count[feature_type] = count.get(feature_type,0) + 1
            name = ID + "." + feature_type +"." + str(count[feature_type])
            sub.qualifiers['ID'] = name
            sub.qualifiers['Parent'] = ID
            sub.qualifiers.pop('Name')
            sub.qualifiers['source'] = "apollo"
            format_gene_model(sub.sub_features, sub.qualifiers['ID'], count)

def delete_gene_model(seqfeature, orig_models, idx):

    # logging
    gene_name = seqfeature.qualifiers.get('Name')[0]
    print("delete gene: " + gene_name, file=stderr)

    orig_models[idx].features.remove(seqfeature)

def update_gff(orig_gff, new_gff ):
    orig_models = gff_reader(orig_gff)
    # get the gene and corresponding feature
    orig_models_dict = get_model_dict(orig_models)
    # get reference index in SeqRecord list
    orig_index = {l.id : idx for idx,l in enumerate( orig_models )}

    # read the new model from apollo exported gff
    new_models  = gff_reader(new_gff)
    for rec in new_models:
        idx = orig_index[rec.id]
        for feature in rec.features:
            gene_name = feature.qualifiers.get('description')
            # only use the gene with description information
            if gene_name is None:
                continue
            gene_name = gene_name[0]
            # delete the gene
            if gene_name.find('delete') > 0:
                gene_name = gene_name[0:gene_name.find('delete')-1]
                sf = orig_models_dict.get(gene_name)
                delete_gene_model(sf, orig_models, idx)
            # modify the existed gene
            elif gene_name in orig_models_dict.keys():
                sf = orig_models_dict.get(gene_name)
                delete_gene_model(sf, orig_models, idx)
                add_gene_model(feature, orig_models, idx)
            # add new gene
            else:
                add_gene_model(feature, orig_models, idx)

    return orig_models

if __name__ == '__main__':
    args = get_opt()

    new_models = update_gff(args.old_gff, args.new_gff)
    #print("finished!", file=stderr)
    gff_writer(new_models, args.out)

