import pygame
import sys
from settings import *
from game import Player, create_traps

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Магический лабиринт")
    clock = pygame.time.Clock()

    player = Player()
    traps = create_traps()
    all_sprites = pygame.sprite.Group(player, *traps)

    font = pygame.font.SysFont(None, 50)
    game_over = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        if not game_over:
            keys_pressed = pygame.key.get_pressed()
            player.update(keys_pressed)

            # Проверка на столкновение с ловушками
            if pygame.sprite.spritecollideany(player, traps):
                game_over = True

            # Проверка выхода (например, кликаем или достигли определенной точки)
            if player.rect.colliderect(pygame.Rect(750, 550, 50, 50)):
                text = font.render("Вы дошли до выхода!", True, WHITE)
                screen.blit(text, (200, 275))
                pygame.display.flip()
                pygame.time.wait(3000)
                pygame.quit()
                sys.exit()

        # Отрисовка
        screen.fill(BLACK)
        all_sprites.draw(screen)

        # Объявление победы, если достигли выхода
        if player.rect.colliderect(pygame.Rect(750, 550, 50, 50)):
            text = font.render("Вы дошли до выхода!", True, WHITE)
            screen.blit(text, (200, 275))

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    main()