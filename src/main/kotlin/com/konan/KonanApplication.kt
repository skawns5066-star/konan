package com.konan

import org.springframework.boot.autoconfigure.SpringBootApplication
import org.springframework.boot.runApplication

@SpringBootApplication
class KonanApplication

fun main(args: Array<String>) {
    runApplication<KonanApplication>(*args)
}
