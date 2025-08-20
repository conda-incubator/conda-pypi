# Name Mappings Implementation and PURL Roadmap

## Executive Summary

This document outlines the strategic roadmap and engineering decision record
for solving PyPI-conda mappings in the `conda-pypi` project.

The goal is to establish a known path forward to enrich the conda ecosystem
with better tooling to integrate with PyPI.  Eventually, we hope this effort
will lead the community to establish a source of truth for package identification
across the conda entire ecosystem.

## Background and Context

### Current State
- **Existing Mapping Solutions**: grayskull, cf-graph-countyfair, parselmouth
- **Limitations**: All rely on different heuristics with different levels of coverage (all are missing sources for the main channel provided by Anaconda)
- **Problem**: Inconsistent/Incomplete PyPI ↔ conda package mappings

### Short Term and Long Term Roadmap

- **Short Term**
  - Provide basic mapping to allow for MVP functionality
- **Long Term**
  - Establish standards and processes for the entire community so mapping for any ecosystem is done as part of the process.
  - Eventually, we should look to standardize using [Package URLs](https://github.com/package-url/purl-spec)

### Why PURLs?
- **Standardization**: PURLs provide a universal way to identify packages
- **Future-Proof**: Aligns with emerging Python packaging standards (PEP 725)
- **Scales**: This scales to other ecosystems that the conda community could be interested in (i.e. CRAN)
  - conda-pypi could become a model to extend this type of for other ecosystems.


## Implementation Roadmap

For any solution to be possible, conda-pypi will need a PyPI->conda name mapping:
- Existence and Access
- Continual Updates
- It would be best to have this done by channel as (but we could get by without for now):
   - Names are not guaranteed to be the same across channels, nor have the same sources
   - Different users use different channels

Outstanding Questions that need to be answered:

- [ ] Where will this name mapping be stored?
  - Currently, Prefix hosts `parselmouth` data but that is only for specific channels (conda-forge and 2 others) also conda-forge does the stores its data in cf-graph-county-fair
  - Another source of data could be used for the main channel
  - Another possibility is to store this information in repodata.json, this would require an ecosystem change.

- [ ] How will the name mapping be accessed?
  - For conda-forge and Prefix, the data can be accessed directly from github.  Prefix has gone one step more by hosting an API service to look up.
  - Again, having the data in repodata.json makes this simpler but not as easy.


### Phase 1: MVP Implementation

#### 1.1 Hardcoded Mapping System (we get this for free from conda-pupa)
- [ ] Update pypi->conda mappings from cf-graph-countyfair
- [ ] Convert cf-graph-county fair mappings into a Purl mapping style:
  - **Alternatively**, we could skip this step for now.  Though this small step will put us a little closer to native conda install support

### Phase 2: Mapping Foundation

#### 2.1 PURL CEP Exploration
- [ ] Explore POC for using CEP (PR 63 and 114) as a basis for mapping
- [ ] Key stakeholder discussions and CEP refinements

Expected Outcomes from PURL CEP exploration
- [ ] Decision on how and where PURL's are stored and accessed
- [ ] Decision on any PURL standards (such as storing PURL as a service or in repodata.json)
- [ ] Reverse Mapping Storage???
  - There are times (like our conda-pypi case) where it is better to have the reverse mapping handy.  Where would this be stored, if at all?

#### 2.2 PURL POC
- [ ] Proof of concept implementation

Expected Outcomes:
- [ ] Further refinement of CEP for PURL
- [ ] Implementation Plan of Name Mapping feature

### Phase 3: Mapping Implementation

#### 3.1 CEP Adoption

- Whichever path forward is chosen should be adopted formally as a CEP

#### 3.2 CEP Implementation

- TBD on steps.

#### 3.3 Backporting Support

- Any backports should be done as required
