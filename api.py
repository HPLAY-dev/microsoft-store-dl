import requests
from bs4 import BeautifulSoup


getfiles_url = 'https://store.rg-adguard.net/api/GetFiles'
payload = {
    'type': 'ProductId',
    'url': '9pnrbtzxmb4z',
    'ring': 'RP',
    'lang': 'en-US'
}


def parse_raw(html_content):
    """解析 store.rg-adguard.net 返回的HTML并提取"""
    soup = BeautifulSoup(html_content, 'html.parser')
    file_list = []
    
    # 定位包含文件信息的表格
    table = soup.find('table', class_='tftable')
    if not table:
        return file_list
    
    # 找到表格中所有的行（跳过表头）
    rows = table.find_all('tr')[1:]  # 跳过第一个表头行
    
    for row in rows:
        # 获取该行所有单元格
        cells = row.find_all('td')
        if len(cells) >= 4:  # 确保有足够的列
            # 第一列：文件名和URL
            link_cell = cells[0]
            link_tag = link_cell.find('a')
            
            if link_tag:
                file_name = link_tag.text.strip()
                file_url = link_tag.get('href', '').strip()
                
                # 第二列：过期时间
                expire_time = cells[1].text.strip()
                
                # 第四列：文件大小（跳过第三列的SHA-1）
                file_size = cells[3].text.strip()
                
                # 添加到结果列表
                file_list.append({
                    'name': file_name,
                    'url': file_url,
                    'time': expire_time,
                    'size': file_size
                })
    
    return file_list

def request_files_raw(url, url_type='ProductId', lang='en_US'):
    """从store.rg-adguard.net把文件扒过来"""
    if url == None:
        print('Bad URL')
    getfiles_url = 'https://store.rg-adguard.net/api/GetFiles'
    payload = {
        'type': url_type,
        'url': url,
        'ring': 'RP',
        'lang': lang
    }
    i = requests.post(getfiles_url, data=payload)
    return i.text

def get_files(url, url_type='ProductId', lang='en_US'):
    return parse_raw(request_files_raw(url_type=url_type, url=url, lang=lang))