import pygame
from pygame.locals import *
import fafvn

pygame.mixer.pre_init(buffer=2048)
pygame.init()
pygame.mixer_music.set_volume(fafvn.BMG_BASE_VOLUME)

TIMER = pygame.time.Clock()


fafvn.NAME_FONT = pygame.font.SysFont("comicsansms", 35)
fafvn.SAY_FONT = pygame.font.SysFont("comicsansms", 30)

fafvn.Scene.load("chapter1")

print(fafvn.charaZBuffer)

charaTextBox = fafvn.UIElement("./Assets/UI/CharaTextBox.png")

### GAME LOOP ###
keepRunning = True

while keepRunning:
    fafvn.eventList = pygame.event.get()
    for event in fafvn.eventList:
        if event.type == QUIT:
            keepRunning = False
        if fafvn.Scene.paused == False:
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:    # LEFT CLICK
                fafvn.Scene.advance()                    
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    fafvn.Scene.advance()
        if event.type == pygame.MOUSEBUTTONUP and event.button == 2:    # MIDDLE CLICK
                fafvn.Scene.appreciationMode()
                print("MIDDLE CLICK")
        if event.type == pygame.MOUSEBUTTONUP and event.button == 3:    # RIGHT CLICK
            print("RIGHT CLICK")
    
    TIMER.tick(fafvn.FPS)

    fafvn.Scene.checkCollisions()
    fafvn.Scene.update()
    pygame.display.flip()