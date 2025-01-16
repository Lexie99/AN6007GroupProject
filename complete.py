import csv

class Elecdata():
    def __init__(self,region,area,year,month,dwelling_type,kwh_per_acc):
        self.region = region
        self.area = area
        self.year = year
        self.month = month
        self.dwelling_type = dwelling_type
        self.kwh_per_acc = kwh_per_acc
    def __repr__(self):
        return f"Region:{self.region}, Area:{self.area}, Year:{self.year}, Month:{self.month}, Type:{self.dwelling_type}, kwh_per_acc:{self.kwh_per_acc}"

def load_area_dict():
    with open('Area.txt') as f:
        return {line.split(';')[0]: {'Area': line.split(';')[1].strip(), 'Region': line.split(';')[2].strip()} for line in f}

def load_dwelling_dict():
    dwelling_dict = {}
    with open('Dwelling.txt') as f:
        for line in f:
            if not line.startswith("TypeID"):
                type_id, dwelling_type = line.strip().split(',')
                dwelling_dict[type_id] = dwelling_type
    return dwelling_dict

def load_datedim_dict():
    with open('DateDim.txt') as f:
        return {line.split(';')[0]: {'Year': line.split(';')[1].strip(), 'Month': line.split(';')[2].strip(), 'Quarter': line.split(';')[3].strip()} for line in f}

def load_electricity_dict():
    with open('Electricity.txt') as f:
        return [{'DateID': line.split(';')[0].strip(),
                 'AreaID': line.split(';')[1].strip(),
                 'Dwelling_Type_ID': line.split(';')[2].strip(),
                 'kwh_per_acc': float(line.split(';')[3].strip())} for line in f if not line.startswith("DateID")]

def merge_data():
    area = load_area_dict()
    dwelling = load_dwelling_dict()
    datedim = load_datedim_dict()
    electricity = load_electricity_dict()

    merged_data = []
    for record in electricity:
        area_info = area[record['AreaID']]
        dwelling_type = dwelling[record['Dwelling_Type_ID']]
        date_info = datedim[record['DateID']]

        merged_record = {
            'Region': area_info['Region'],
            'Area': area_info['Area'],
            'Year': date_info['Year'],
            'Month': date_info['Month'],
            'Dwelling_Type': dwelling_type,
            'kwh_per_acc': record['kwh_per_acc']
        }
        merged_data.append(merged_record)
    
    return merged_data

def create_objects_dict(merged_data):
    object_list = []
    for record in merged_data:
        obj = Elecdata(region=record['Region'],
                       area=record['Area'],
                       year=record['Year'],
                       month=record['Month'],
                       dwelling_type=record['Dwelling_Type'],
                       kwh_per_acc=record['kwh_per_acc'])
        object_list.append(obj)
    return object_list

def sort_data(data):
    return sorted(data, key=lambda x: (x.area, int(x.year), int(x.month), x.dwelling_type))

def export_to_csv(dataset, filename='dashboard.csv'):
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Region', 'Area', 'Year', 'Month', 'Dwelling_Type', 'kwh_per_acc'])
        for data in dataset:
            writer.writerow([data.region, data.area, data.year, data.month, data.dwelling_type, data.kwh_per_acc])

if __name__ == '__main__':
    load_area_dict()
    load_dwelling_dict()
    load_datedim_dict()
    load_electricity_dict()
    merged_data = merge_data()
    object_list = create_objects_dict(merged_data)  
    dwelling_dict = {"1": "1-room / 2-room","2": "Private Apartments and Condominiums","3": "Landed Properties","4": "5-room and Executive","5": "3-room","6": "4-room"}
    dataset = sort_data(object_list)
    export_to_csv(dataset)
    


    