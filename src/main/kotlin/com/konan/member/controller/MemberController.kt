package com.konan.member.controller

import com.konan.member.dto.MemberRequest
import com.konan.member.dto.MemberResponse
import com.konan.member.service.MemberService
import jakarta.validation.Valid
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.DeleteMapping
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.servlet.support.ServletUriComponentsBuilder

@RestController
@RequestMapping("/api/members")
class MemberController(
    private val memberService: MemberService,
) {
    @PostMapping
    fun create(@Valid @RequestBody request: MemberRequest): ResponseEntity<MemberResponse> {
        val created = memberService.create(request)
        val location = ServletUriComponentsBuilder.fromCurrentRequest()
            .path("/{id}")
            .buildAndExpand(created.id)
            .toUri()
        return ResponseEntity.created(location).body(created)
    }

    @GetMapping
    fun findAll(): List<MemberResponse> = memberService.findAll()

    @GetMapping("/{id}")
    fun findById(@PathVariable id: Long): MemberResponse = memberService.findById(id)

    @PutMapping("/{id}")
    fun update(@PathVariable id: Long, @Valid @RequestBody request: MemberRequest): MemberResponse =
        memberService.update(id, request)

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun delete(@PathVariable id: Long) = memberService.delete(id)
}
