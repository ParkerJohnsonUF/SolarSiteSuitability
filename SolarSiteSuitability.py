import arcpy
from arcpy import env
from arcpy.sa import *
import sys
import datetime

# Setup Workspace (location where tool outputs will be stored) ##
Workspace = arcpy.GetParameterAsText(0)

env.workspace = Workspace

# -- Overwrite Command -- # 
Overwrite = arcpy.GetParameterAsText(1)
if Overwrite.lower() == "true":
    arcpy.env.overwriteOutput = True
    arcpy.AddMessage("Overwriting existing features")
else:
    arcpy.env.overwriteOutput = False
    arcpy.AddMessage("Do not overwrite existing features")
    
## -- Inputs Parameters for County Selection -- ##

CountyName = arcpy.GetParameterAsText(2) # PARAMETER TYPE:  INPUT - STRING

CountyNumber = arcpy.GetParameterAsText(3) # PARAMETER TYPE: INPUT - INTEGER

### ---------------------------------------------LAND DATA ANALYSIS-------------------------------------------------###



allcounties = arcpy.GetParameterAsText(4) # PARAMETER TYPE: INPUT - FEATURE CLASS

expression = "NAME = '{}'".format(CountyName)

arcpy.AddMessage("Creating Extent")

CountySelect = arcpy.management.SelectLayerByAttribute(allcounties, 'NEW_SELECTION', expression)
CountyExtent = arcpy.management.CopyFeatures(CountySelect, "{}.shp".format(CountyName))

arcpy.AddMessage("Extent creation completed")


#----------EXCLUSION AREAS---------#

# --- Parks

parks = arcpy.GetParameterAsText(5)  # PARAMETER TYPE: INPUT - FEATURE CLASS

park_select = arcpy.management.SelectLayerByAttribute(parks, "NEW_SELECTION", "COUNTY = '{}'".format(CountyName))
parks_selection = arcpy.management.CopyFeatures(park_select, "{}Parks".format(CountyName))

parks_buffer = arcpy.analysis.Buffer(parks_selection, "ParksBuffer", "5")

# ---Trails
trails = arcpy.GetParameterAsText(6)  # PARAMETER TYPE: INPUT - FEATURE CLASS

trails_select = arcpy.management.SelectLayerByAttribute(trails, "NEW_SELECTION", "COUNTY = '{}'".format(CountyName))
trails_selection = arcpy.management.CopyFeatures(trails_select, "{}Trails".format(CountyName))

trails_buffer = arcpy.analysis.Buffer(trails_selection, "TrailsBuffer", "5")

# --- Conservation

conservation = arcpy.GetParameterAsText(7)  # PARAMETER TYPE: INPUT - FEATURE CLASS

conservation_select = arcpy.management.SelectLayerByAttribute(conservation, "NEW_SELECTION", "COUNTY = '{}'".format(CountyName[0:3]))
conservation_selection = arcpy.management.CopyFeatures(conservation_select, "{}Conservation".format(CountyName))

conservation_buffer = arcpy.analysis.Buffer(conservation_selection, "ConservationBuffer", "5")

# ---Wetlands

wetlands = arcpy.GetParameterAsText(8)  # PARAMETER TYPE: INPUT - FEATURE CLASS

wetlands_select = arcpy.management.SelectLayerByLocation(wetlands, 'COMPLETELY_WITHIN', CountyExtent)
wetlands_selection = arcpy.management.CopyFeatures(wetlands_select, "{}Wetlands".format(CountyName))

wetlands_buffer = arcpy.analysis.Buffer(wetlands_selection, "WetlandsBuffer", "5")

# --- Union Buffers for Exclusion Areas
infeatures = [parks_buffer, trails_buffer, conservation_buffer, wetlands_buffer]
outfeature = "ExclusionArea"
exclusion = arcpy.analysis.Union(infeatures, outfeature)

#####---------- INCLUSION AREAS ----------#####

# ---Roads
roads = arcpy.GetParameterAsText(9)  # PARAMETER TYPE: INPUT - FEATURE CLASS

roads_select = arcpy.management.SelectLayerByLocation(roads, 'INTERSECT', CountyExtent)
roads_selection = arcpy.management.CopyFeatures(roads_select, "Roads")

roads_clip = arcpy.analysis.Clip(roads_selection, CountyExtent, "{}Roads".format(CountyName))
roads_buffer = arcpy.analysis.Buffer(roads_clip, "RoadsBuffer", "804.5")

# ---Powerlines
powerlines = arcpy.GetParameterAsText(10)  # PARAMETER TYPE: INPUT - FEATURE CLASS

powerlines_select = arcpy.management.SelectLayerByLocation(powerlines, 'INTERSECT', CountyExtent)
powerlines_selection = arcpy.management.CopyFeatures(powerlines_select, "Powerlines")

powerlines_clip = arcpy.analysis.Clip(powerlines_selection, CountyExtent, "{}Powerlines".format(CountyName))
powerlines_buffer = arcpy.analysis.Buffer(powerlines_clip, "PowerlinesBuffer", "1609")

# --- Merge Inclusion Buffers for Inclusion Areas
mergeinput = [roads_buffer, powerlines_buffer]
mergeoutput = "Inclusion_Areas"
inclusion = arcpy.management.Merge(mergeinput, mergeoutput)

# --- Erase Exclusion Areas from Inclusion Areas for suitable land (not considering land use)

noLUsuitfc = "SuitnoLU"

noLUsuit = arcpy.analysis.Erase(inclusion, exclusion, noLUsuitfc)



# ------ Land Use Analysis ----- #

#--- Select Desired County
landuse = arcpy.GetParameterAsText(11)

luexpression = "CNTYNAME = '{}'".format(CountyName)
landuse_select = arcpy.management.SelectLayerByAttribute(landuse, 'NEW_SELECTION', luexpression)

landuse_selection = arcpy.management.CopyFeatures(landuse_select, "LandUse")

#--- Add Field "LU_SCORE" to update field score based on land use description

arcpy.management.AddField(landuse_selection, "LU_SCORE", "SHORT", "", "", "5", "LU_SCORE")

suit = ["ACREAGE NOT ZONED FOR AGRICULTURE",
        "PARCELS WITH NO VALUES",
        "PUBLIC/SEMI-PUBLIC",
        "RESIDENTIAL",
        "VACANT NONRESIDENTIAL",
        "VACANT RESIDENTIAL"]

not_suit = ["AGRICULTURAL",
            "INDUSTRIAL",
            "INSTITUTIONAL",
            "MINING",
            "NO DATA AVAILABLE",
            "OTHER",
            "RECREATION",
            "RETAIL/OFFICE",
            "ROW",
            "WATER"]

#--- Use Update Cursor to update LU_Score Field based on DESCRIPT field

featureclass = landuse_selection

fields = ["DESCRIPT", "LU_SCORE"]

with arcpy.da.UpdateCursor(featureclass, fields) as cursor:

    for row in cursor:
        descript = row[0]
        if descript in suit:
            row[1] = 9

        elif descript in not_suit:
            row[1] = 1

        cursor.updateRow(row)
        
#--- Create Suitable Land Use Layer from records with a LU_SCORE value of 9

suitLUselect = arcpy.management.SelectLayerByAttribute(landuse_selection, 'NEW_SELECTION', "LU_SCORE = 9")
suitLU = arcpy.management.CopyFeatures(suitLUselect, "SuitableLU")

### ----- INTERSECT SUITLU AND LUNOSUIT FOR FINAL SUITABLE LANDS -----#####

# suitable land USE is 'suitLU'
# suitable LAND is 'noLUsuit'

SuitableLand = arcpy.analysis.Clip(suitLU, noLUsuit, "SuitableLand") # NEEDS TO BE CHANGED TO A CLIP


#####---------------------------------------COMMUNITY ANALYSIS--------------------------------------------------------#####


#Income Rasterization
income = arcpy.GetParameterAsText(12)   # PARAMETER TYPE: INPUT - FEATURE CLASS

CountyIncome = arcpy.management.SelectLayerByAttribute(income, 'NEW_SELECTION', "COUNTYFP = '{}'".format(CountyNumber))
income_selection = arcpy.management.CopyFeatures(CountyIncome, "Income")

income_raster = arcpy.conversion.FeatureToRaster(income_selection, "MEDHHINC", "IncomeRaster", "10")

#Parcel Rasterization
 
parcels = arcpy.GetParameterAsText(13)   # PARAMETER TYPE: INPUT - FEATURE CLASS

CountyParcels = arcpy.management.SelectLayerByAttribute(parcels, 'NEW_SELECTION', "CNTYNAME = '{}'".format(CountyName))
parcel_selection = arcpy.management.CopyFeatures(CountyParcels, "{}Parcels".format(CountyName))

parcel_raster = arcpy.conversion.FeatureToRaster(parcel_selection, "ACTYRBLT", "ParcelRaster", "10")

#Housing Rasterization

housing_exp = arcpy.GetParameterAsText(14)    # PARAMETER TYPE: INPUT - FEATURE CLASS

County_exp = arcpy.management.SelectLayerByAttribute(housing_exp, 'NEW_SELECTION', "COUNTY = '{}'".format(CountyNumber))
exp_selection = arcpy.management.CopyFeatures(County_exp, "{}_exp".format(CountyName))

exp_raster = arcpy.conversion.FeatureToRaster(exp_selection, "hh1_h", "ExpRaster", "10")

### ----- RECLASSIFYING RASTER VALUES FOR RASTER LAYERS IN COMMUNITY ANALYSIS ----- ###

#income is income_raster
inraster = income_raster
reclass_field = "VALUE"
remap = "0 15359.237612 1; 15359.237612 26321.123684 2;26321.123684 34144.620481 3;34144.620481 39728.249223 4;39728.249223 47551.746020 5;47551.746020 58513.632092 6;58513.632092 73872.869704 7;73872.869704 95393.452791 8;95393.452791 2000000  9"
outraster = "Rec_Income"
income_reclass = arcpy.ddd.Reclassify(inraster, reclass_field, remap, outraster, "DATA")

#parcels parcels_raster
inraster2 = parcel_raster
reclass_field2 = "VALUE"
remap2 = "0 1939 1;1939 1949 2;1949 1959 3;1959 1969 4;1969 1979 5;1979 1989 6;1989 1999 7;1999 2009 8;2009 2020 9"
outraster2 = "Rec_Parcels"
parcel_reclass = arcpy.ddd.Reclassify(inraster2, reclass_field2, remap2, outraster2, "DATA")

#housingexp exp_raster
inraster3 = exp_raster
reclass_field3 = "VALUE"
remap3 = "0 23.550381 9;23.550381 24.309201 8;24.309201 24.771896 7;24.771896 25.054028 6;25.054028 25.226059 5;25.226059 25.508190 4;25.508190 25.970886 3;25.970886 26.729706 2;26.729706 50 1"
outraster3 = "Rec_HExp"
exp_reclass = arcpy.ddd.Reclassify(inraster3, reclass_field3, remap3, outraster3, "DATA")

### PERFORMING WEIGHTED SUM ON RECLASSIFIED RASTERS FOR COMMUNITY ANALYSIS ### 

#set parameters
IncomeWeight = arcpy.GetParameterAsText(15)   # PARAMATER TYPE - INPUT WEIGHTED SUM VALUE
ParcelWeight = arcpy.GetParameterAsText(16)   # PARAMATER TYPE - INPUT WEIGHTED SUM VALUE
ExpWeight = arcpy.GetParameterAsText(17)     # PARAMATER TYPE - INPUT WEIGHTED SUM VALUE

WSumTableObj = WSTable([[income_reclass, "VALUE", IncomeWeight], 
                        [parcel_reclass, "VALUE", ParcelWeight], 
                        [exp_reclass, "VALUE", ExpWeight]])

#execute weighted sum

CommunitySuitability = arcpy.sa.WeightedSum(WSumTableObj)
CommunitySuitability.save("Comm_Suit")

### EXTRACTING TARGET NEIGHBORHOODS FROM COMMUNITY SUITABILITY RASTER ###


# --- convert raster values to whole numbers

comraster = CommunitySuitability

IntRaster = arcpy.sa.Int(comraster)
IntRaster.save("INTcomm_suit")

# --- Extract all cells with value of 1 - 3 to identify target neighborhoods

attExtract = arcpy.sa.ExtractByAttributes(IntRaster, "VALUE <= 3")
attExtract.save("Disadvantaged")

### CONVERTING DISADVANTAGED RASTER LAYER TO POLYGON IN ORDER TO PERFORM SPATIAL ANALYSIS

TargetArea = arcpy.conversion.RasterToPolygon(attExtract, "TargetAreas", "NO_SIMPLIFY", "VALUE")

## Buffering Target Area to allow for more potential sites

TargetAreaBuffer = arcpy.analysis.Buffer(TargetArea, "TotalArea", "400")

# Dissolving Target Area Buffer Layer by Value (1-3) to reduce records

DissolveTargetArea = arcpy.management.Dissolve(TargetAreaBuffer, "TotalAreaDiss", "gridcode")

# creating final sites layer by selecting suitable land within the dissolve target area buffer

FinalSiteSelect = arcpy.management.SelectLayerByLocation(SuitableLand,'COMPLETELY_WITHIN', DissolveTargetArea)
FinalSiteSelection = arcpy.management.CopyFeatures(FinalSiteSelect, "FinalSites")

