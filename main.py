import cv2
from keyboard import Keyboard
import numpy as np
from windowcapture import WindowCapture
import asyncio
from time import time
import threading

# I don't know why 33x33 and 32x32, forget about it
template_click = cv2.imread('click.png', cv2.IMREAD_UNCHANGED)
template_click = cv2.resize(template_click, (33, 33))
hh_click, ww_click = template_click.shape[:2]

pawn_click = template_click[:, :, 0:3]
alpha_click = template_click[:, :, 3]
alpha_click = cv2.merge([alpha_click, alpha_click, alpha_click])

template_hold = cv2.imread('hold.png', cv2.IMREAD_UNCHANGED)
template_hold = cv2.resize(template_hold, (32, 32))
hh_hold, ww_hold = template_hold.shape[:2]

pawn_hold = template_hold[:, :, 0:3]
alpha_hold = template_hold[:, :, 3]
alpha_hold = cv2.merge([alpha_hold, alpha_hold, alpha_hold])

what_need_to_do = {}
hold_exists_frames = {}
holding_btn = {}

keyboard = Keyboard()

wincap = WindowCapture('Genshin Impact')

delay_for_sector = {}
delay_input = 0.05


def click_thread(sector):
    if sector in delay_for_sector:
        if time() - delay_for_sector[sector] > delay_input:
            del delay_for_sector[sector]

    if sector not in delay_for_sector:
        keyboard.KeyPress(sector)
        delay_for_sector[sector] = time()


def keydown_thread(sector):
    if sector in delay_for_sector:
        if time() - delay_for_sector[sector] > delay_input:
            del delay_for_sector[sector]

    if sector not in delay_for_sector:
        keyboard.KeyDown(sector)
        delay_for_sector[sector] = time()


def keyup_thread(sector):
    if sector in delay_for_sector:
        if time() - delay_for_sector[sector] > delay_input:
            del delay_for_sector[sector]

    if sector not in delay_for_sector:
        keyboard.KeyUp(sector)
        delay_for_sector[sector] = time()


async def main():
    loop_time = time()
    while True:
        frame = wincap.get_image_from_window()

        # PlayCover size is 1512x945
        img = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)

        hhh, www = img.shape[:2]

        # Padding for center of first sector
        left_padding = 120
        bottom_padding = 55

        img = img[hhh - bottom_padding - 20 - 20:hhh - bottom_padding + 30, left_padding - 30:www - left_padding + 30]

        hhh, www = img.shape[:2]
        bounding_box_top = hhh - 25 - 30
        bounding_box_bottom = hhh - 10

        result = img.copy()

        # Sectors
        sep_distance = www // 6
        for sep in range(0, 6):
            cv2.rectangle(result, (sep * sep_distance, 0), (sep * sep_distance + sep_distance, hhh), (0, 0, 255), 1)

        # Click and hold area for perfect score
        cv2.rectangle(result, (0, bounding_box_bottom), (www, bounding_box_top), (0, 255, 255), 1)

        correlation_click = cv2.matchTemplate(img, pawn_click, cv2.TM_CCORR_NORMED, mask=alpha_click)
        correlation_hold = cv2.matchTemplate(img, pawn_hold, cv2.TM_CCORR_NORMED, mask=alpha_hold)

        threshold = 0.96
        sector_bounding_boxes = {}

        loc_click = np.where(correlation_click >= threshold)
        loc_hold = np.where(correlation_hold >= threshold)

        for pt in zip(*loc_click[::-1]):
            sector = pt[0] // (result.shape[1] // 6)
            if sector not in sector_bounding_boxes:
                sector_bounding_boxes[sector] = [pt, (pt[0] + ww_click, pt[1] + hh_click)]
            else:
                tl_x, tl_y = sector_bounding_boxes[sector][0]
                br_x, br_y = sector_bounding_boxes[sector][1]
                sector_bounding_boxes[sector] = [(min(tl_x, pt[0]), min(tl_y, pt[1])),
                                                 (max(br_x, pt[0] + ww_click), max(br_y, pt[1] + hh_click))]
            cv2.rectangle(result, pt, (pt[0] + ww_click, pt[1] + hh_click), (0, 255, 0), 1)
            what_need_to_do[sector] = 'click'

        for pt in zip(*loc_hold[::-1]):
            sector = pt[0] // (result.shape[1] // 6)
            if sector not in sector_bounding_boxes:
                sector_bounding_boxes[sector] = [pt, (pt[0] + ww_hold, pt[1] + hh_hold)]
            else:
                tl_x, tl_y = sector_bounding_boxes[sector][0]
                br_x, br_y = sector_bounding_boxes[sector][1]
                sector_bounding_boxes[sector] = [(min(tl_x, pt[0]), min(tl_y, pt[1])),
                                                 (max(br_x, pt[0] + ww_hold), max(br_y, pt[1] + hh_hold))]

            cv2.rectangle(result, pt, (pt[0] + ww_click, pt[1] + hh_click), (0, 255, 0), 1)
            center = ((sector_bounding_boxes[sector][0][0] + sector_bounding_boxes[sector][1][0]) // 2,
                      (sector_bounding_boxes[sector][0][1] + sector_bounding_boxes[sector][1][1]) // 2)

            hold_exists_frames[sector] = 10
            if center[1] in range(bounding_box_top, bounding_box_bottom):
                what_need_to_do[sector] = 'hold'

        current_action = []
        for sep in range(0, 6):
            if sep in what_need_to_do:
                action = what_need_to_do[sep]
                if action == 'click':
                    if sep in sector_bounding_boxes:
                        sector = sector_bounding_boxes[sep]
                        center = ((sector[0][0] + sector[1][0]) // 2, ((sector[0][1] + sector[1][1]) // 2) + 15)
                        if center[1] in range(bounding_box_top, bounding_box_bottom):
                            current_action.append({
                                'action': 'click',
                                'sector': str(sep + 1)
                            })
                            cv2.putText(result, action, (sep * sep_distance + 10, bounding_box_bottom - 20),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
                            del what_need_to_do[sep]
                if action == 'hold':
                    if hold_exists_frames and sep in hold_exists_frames:
                        if hold_exists_frames[sep] > 0:
                            cv2.putText(result, action, (sep * sep_distance + 10, bounding_box_bottom - 15),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                            hold_exists_frames[sep] -= 1
                            if sep not in holding_btn:

                                current_action.append({
                                    'action': 'down',
                                    'sector': str(sep + 1)
                                })

                                holding_btn[sep] = True
                        else:
                            if sep in holding_btn:
                                current_action.append({
                                    'action': 'up',
                                    'sector': str(sep + 1)
                                })
                            del holding_btn[sep]
                            del hold_exists_frames[sep]
                            del what_need_to_do[sep]

        for action in current_action:
            if action['action'] == 'click':
                threading.Thread(target=click_thread, args=(action['sector'],)).start()
            if action['action'] == 'down':
                threading.Thread(target=keydown_thread, args=(action['sector'],)).start()
            if action['action'] == 'up':
                threading.Thread(target=keyup_thread, args=(action['sector'],)).start()

        cv2.imshow('Video', result)

        print('FPS {}'.format(1 / (time() - loop_time)))

        loop_time = time()

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

if __name__ == '__main__':
    asyncio.run(main())
