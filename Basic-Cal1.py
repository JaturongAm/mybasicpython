tilecolor = {'red':100,'gold':200,'white':90}
print('-------โปรแกรมคำนวณกระเบื้อง by Jaturong--------')

try:
    tiles=int(input('คุณต้องการปูกระเบื้องทั้งหมดกี่แผ่น: '))
    row=int(input('1 แถวต้องปูทั้งหมดกี่แผ่น: '))
    color = input('กระเบื้องสีอะไร? [red/gold/white]: ')
except:
    print('กรุณากรอกเป็นตัวเลขเท่านั้น')
    tiles=int(input('คุณต้องการปูกระเบื้องทั้งหมดกี่แผ่น: '))
    row=int(input('1 แถวต้องปูทั้งหมดกี่แผ่น: '))
    color = input('กระเบื้องสีอะไร? [red/gold/white]: ')
    
print('-------คำนวณ--------')
total_row=tiles//row
remain_tiles = tiles%row

buy_more = row-remain_tiles
print(f'กระเบื้องทั้งหมด: {tiles} แผ่น')
print(f'1 แถวปูกระเบื้องได้ {row} แผ่น')
print('-------คำนวณ--------')
print('ต้องปูกระเบื้องทั้งหมด {} แถว'.format(total_row))
print('เหลือกระเบื้องที่ยังไม่ได้ปูเต็มแถว {} แผ่น'.format(remain_tiles))
print('ลูกค้าต้องซื้อกระเบื้องเพิ่ม {} แผ่น'.format(buy_more))
print('ยอดรวมทั้งหมดที่ต้องซื้อกระเบื้องเพิ่ม {} บาท'.format(buy_more*tilecolor[color]))

pring('---------------------The End-------------------------')
