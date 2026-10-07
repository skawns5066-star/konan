package com.konan.member.service

import com.konan.member.domain.Member
import com.konan.member.dto.MemberRequest
import com.konan.member.dto.MemberResponse
import com.konan.member.repository.MemberRepository
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional

@Service
@Transactional(readOnly = true)
class MemberService(
    private val memberRepository: MemberRepository,
) {
    @Transactional
    fun create(request: MemberRequest): MemberResponse {
        if (memberRepository.existsByEmail(request.email)) {
            throw DuplicateEmailException(request.email)
        }
        val member = memberRepository.save(Member(name = request.name, email = request.email))
        return MemberResponse.from(member)
    }

    fun findAll(): List<MemberResponse> =
        memberRepository.findAll().map(MemberResponse::from)

    fun findById(id: Long): MemberResponse =
        MemberResponse.from(getMember(id))

    @Transactional
    fun update(id: Long, request: MemberRequest): MemberResponse {
        val member = getMember(id)
        if (memberRepository.existsByEmailAndIdNot(request.email, id)) {
            throw DuplicateEmailException(request.email)
        }
        member.update(request.name, request.email)
        return MemberResponse.from(member)
    }

    @Transactional
    fun delete(id: Long) {
        memberRepository.delete(getMember(id))
    }

    private fun getMember(id: Long): Member =
        memberRepository.findById(id).orElseThrow { MemberNotFoundException(id) }
}

class MemberNotFoundException(id: Long) : RuntimeException("Member not found: $id")

class DuplicateEmailException(email: String) : RuntimeException("Email already in use: $email")
