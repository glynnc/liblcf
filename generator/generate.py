#!/usr/bin/env python

from __future__ import division

import sys
import os
import re

csv_dir = 'csv'
tmpl_dir = 'templates'
srcdir = '../src/generated.tmp'
hdrdir = srcdir
dstdir = '../src/generated'
enum_introspection = False

class Template(object):
    def __init__(self, filename):
        with open(os.path.join(tmpl_dir, filename), 'r') as f:
            name = None
            value = None
            for line in f:
                if line[0] == '@':
                    if name is not None:
                        setattr(self, name, value)
                    name = line[1:].rstrip('\r\n')
                    value = ''
                else:
                    value += line
            if name is not None:
                setattr(self, name, value)

copy = Template('copyright.tmpl')
reader = Template('reader.tmpl')
ctor = Template('constructor.tmpl')
decl = Template('declaration.tmpl')
decl2 = Template('declaration.tmpl')
chunk = Template('chunks.tmpl')
freader = Template('flag_reader.tmpl')

decl2.enum_header = decl.enum2_header
decl2.enum_tmpl = decl.enum2_tmpl
decl2.enum_footer = decl.enum2_footer

cpp_types = {
    'Boolean': 'bool',
    'Double': 'double',
    'Integer': 'int',
    'UInt8': 'uint8_t',
    'UInt16': 'uint16_t',
    'UInt32': 'uint32_t',
    'Int16': 'int16_t',
    'String': 'std::string',
    }

def flags_def(struct_name):
    f = ['\t\t\tbool %s;\n' % name for name in flags[struct_name]]
    return 'struct Flags {\n' + ''.join(f) + '\t\t}'

def cpp_type(ty, prefix = True, expand_flags = None):
    if ty in cpp_types:
        return cpp_types[ty]

    m = re.match(r'Array<(.*):(.*)>', ty)
    if m:
        return 'std::vector<%s>' % cpp_type(m.group(1), prefix, expand_flags)

    m = re.match(r'(Vector|Array)<(.*)>', ty)
    if m:
        return 'std::vector<%s>' % cpp_type(m.group(2), prefix, expand_flags)

    m = re.match(r'Ref<(.*):(.*)>', ty)
    if m:
        return cpp_type(m.group(2), prefix, expand_flags)

    m = re.match(r'Ref<(.*)>', ty)
    if m:
        return 'int'

    m = re.match(r'Enum<(.*)>', ty)
    if m:
        return 'int'

    m = re.match(r'(.*)_Flags$', ty)
    if m:
        if expand_flags:
            return flags_def(expand_flags)
        else:
            ty = m.expand(r'\1::Flags')
            if prefix:
                ty = 'RPG::' + ty
            return ty

    if prefix:
        ty = 'RPG::' + ty

    return ty

int_types = {
    'UInt8': 'uint8_t',
    'UInt16': 'uint16_t',
    'UInt32': 'uint32_t',
    'Int16': 'int16_t',
    }

def struct_headers(ty, header_map):
    if ty == 'String':
        return ['<string>']

    if ty in int_types:
        return ['"reader_types.h"']

    if ty in cpp_types:
        return []

    m = re.match(r'Ref<(.*):(.*)>', ty)
    if m:
        return struct_headers(m.group(2), header_map)

    if re.match(r'Ref<(.*)>', ty):
        return []

    if re.match(r'Enum<(.*)>', ty):
        return []

    if re.match(r'(.*)_Flags$', ty):
        return []

    m = re.match(r'Array<(.*):(.*)>', ty)
    if m:
        return ['<vector>'] + struct_headers(m.group(1), header_map)

    m = re.match(r'(Vector|Array)<(.*)>', ty)
    if m:
        return ['<vector>'] + struct_headers(m.group(2), header_map)

    header = header_map.get(ty)
    if header is not None:
        return ['"rpg_%s.h"' % header]

    if ty in ['Parameters', 'Equipment', 'EventCommand', 'MoveCommand', 'Rect', 'TreeMap']:
        return ['"rpg_%s.h"' % ty.lower()]

    return []

def get_structs(filename = 'structs.csv'):
    result = []
    with open(os.path.join(csv_dir, filename), 'r') as f:
        for line in f:
            data = line.strip().split(',')
            filetype, structname, hasid = data
            hasid = bool(int(hasid)) if hasid else None
            filename = structname.lower()
            result.append((filetype, filename, structname, hasid))
    return result

def get_fields(filename = 'fields.csv'):
    result = {}
    with open(os.path.join(csv_dir, filename), 'r') as f:
        for line in f:
            data = line.strip().split(',', 6)
            struct, fname, issize, ftype, code, dfl, comment = data
            issize = issize.lower() == 't'
            code = int(code, 16) if code else None
            if struct not in result:
                result[struct] = []
            result[struct].append((fname, issize, ftype, code, dfl, comment))
    return result

def get_enums(filename = 'enums.csv'):
    enums = {}
    fields = {}
    with open(os.path.join(csv_dir, filename), 'r') as f:
        for line in f:
            data = line.strip().split(',')
            sname, ename, name, num = data
            num = int(num)
            if (sname, ename) not in fields:
                if sname not in enums:
                    enums[sname] = []
                enums[sname].append(ename)
                fields[sname, ename] = []
            fields[sname, ename].append((name, num))
    return enums, fields

def get_flags(filename = 'flags.csv'):
    result = {}
    with open(os.path.join(csv_dir, filename), 'r') as f:
        for line in f:
            data = line.strip().split(',')
            struct, fname = data
            if struct not in result:
                result[struct] = []
            result[struct].append(fname)
    return result

def get_setup(filename = 'setup.csv'):
    result = {}
    with open(os.path.join(csv_dir, filename), 'r') as f:
        for line in f:
            data = line.strip().split(',')
            struct, method, headers = data
            headers = headers.split(' ') if headers else []
            if struct not in result:
                result[struct] = []
            result[struct].append((method, headers))
    return result

def get_headers(structs, sfields, setup):
    header_map = dict([(struct_name, filename)
                       for filetype, filename, struct_name, hasid in structs])
    result = {}
    for filetype, filename, struct_name, hasid in structs:
        if struct_name not in sfields:
            continue
        headers = set()
        for field in sfields[struct_name]:
            fname, issize, ftype, code, dfl, comment = field
            if not ftype:
                continue
            headers.update(struct_headers(ftype, header_map))
        if needs_enums(struct_name):
            headers.add("<string>")
            headers.add("<map>")
            headers.add('"string_less.h"')
        if struct_name in setup:
            for method, hdrs in setup[struct_name]:
                headers.update(hdrs)
        result[struct_name] = sorted(x for x in headers if x[0] == '<') + sorted(x for x in headers if x[0] == '"')
    return result

def write_enums(sname, f):
    for ename in enums[sname]:
        dcl = decl2 if (sname, ename) in [('MoveCommand','Code'),('EventCommand','Code')] else decl
        evars = dict(ename = ename)
        f.write(dcl.enum_header % evars)
        ef = efields[sname, ename]
        n = len(ef)
        for i, (name, num) in enumerate(ef):
            comma = '' if i == n - 1 else ','
            vars = dict(ename = ename,
                        name = name,
                        num = num,
                        comma = comma)
            f.write(dcl.enum_tmpl % vars)
        f.write(dcl.enum_footer % evars)
        if enum_introspection:
            if packed_enum(sname, ename):
                f.write(dcl.names_tmpl % evars)
            else:
                f.write(dcl.names2_tmpl % evars)
            f.write(dcl.names3_tmpl % evars)
    f.write('\n')

def write_setup(sname, f):
    for method, headers in setup[sname]:
        f.write('\t\t%s;\n' % method)

def generate_reader(f, struct_name, vars):
    f.write(copy.header)
    f.write(reader.header % vars)
    for field in sfields[struct_name]:
        fname, issize, ftype, code, dfl, comment = field
        if not ftype:
            continue
        fvars = dict(
            ftype = cpp_type(ftype),
            fname = fname)
        if issize:
            f.write(reader.size_tmpl % fvars)
        else:
            f.write(reader.typed_tmpl % fvars)
    f.write(reader.footer % vars)

def write_flags(f, sname, fname):
    for name in flags[sname]:
        fvars = dict(
            fname = fname,
            name = name)
        f.write(ctor.flags % fvars)

def generate_ctor(f, struct_name, hasid, vars):
    f.write(copy.header)
    f.write(ctor.header % vars)
    if needs_enums(struct_name):
        f.write(ctor.header_map)
    f.write(ctor.header2 % vars)
    if hasid:
        f.write(ctor.tmpl % dict(fname = 'ID', default = '0'))
    for field in sfields[struct_name]:
        fname, issize, ftype, code, dfl, comment = field
        if not ftype:
            continue
        if issize:
            continue
        if ftype.endswith('_Flags'):
            write_flags(f, struct_name, fname)
            continue
        if dfl == '':
            continue
        if ftype.startswith('Vector'):
            continue
        if ftype.startswith('Array'):
            continue
        if ftype == 'Boolean':
            dfl = dfl.lower()
        elif ftype == 'String':
            dfl = '"' + dfl[1:-1] + '"'
        if '|' in dfl:
            # dfl = re.sub(r'(.*)\|(.*)', r'\1', dfl)
            dfl = -1
        fvars = dict(
            fname = fname,
            default = dfl)
        f.write(ctor.tmpl % fvars)
    if struct_name in setup and any('Init()' in method
                                    for method, hdrs in setup[struct_name]):
        f.write('\n\tInit();\n')
    f.write(ctor.footer % vars)

def generate_enums(f, struct_name):
    f.write(ctor.enums);
    for ename in enums[struct_name]:
        if packed_enum(struct_name, ename):
            head = ctor.enum_header
            tmpl = ctor.enum_tmpl
            foot = ctor.enum_footer
        else:
            head = ctor.enum2_header
            tmpl = ctor.enum2_tmpl
            foot = ctor.enum2_footer
        evars = dict(structname = struct_name,
                     ename = ename)
        f.write(head % evars)
        ef = efields[struct_name, ename]
        n = len(ef)
        for i, (name, num) in enumerate(ef):
            comma = '' if i == n - 1 else ','
            vars = dict(name = name,
                        num = num,
                        comma = comma)
            f.write(tmpl % vars)
        f.write(foot % evars)
        f.write(ctor.enum3_header % evars)
        ef = efields[struct_name, ename]
        n = len(ef)
        for i, (name, num) in enumerate(ef):
            comma = '' if i == n - 1 else ','
            vars = dict(name = name,
                        num = num,
                        comma = comma)
            f.write(ctor.enum3_tmpl % vars)
        f.write(ctor.enum3_footer % evars)
    f.write('\n')

def needs_ctor(struct_name, hasid):
    if hasid:
        return True
    for field in sfields[struct_name]:
        fname, issize, ftype, code, dfl, comment = field
        if not ftype:
            continue
        if issize:
            continue
        if ftype.endswith('_Flags'):
            return True
        if dfl != '':
            return True
    return False

def needs_enums(struct_name):
    return enum_introspection and struct_name in enums

def packed_enum(struct_name, ename):
    ef = efields[struct_name, ename]
    n = len(ef)
    for i, (name, num) in enumerate(ef):
        if num != i:
            # print 'enum %s::%s not packed' % (struct_name, ename)
            return False
    return True

def generate_header(f, struct_name, hasid, vars):
    f.write(copy.header)
    f.write(decl.header1 % vars)
    if headers[struct_name]:
        f.write(decl.header2)
        for header in headers[struct_name]:
            f.write(decl.header_tmpl % dict(header = header))
    f.write(decl.header3 % vars)
    if struct_name in enums:
        write_enums(struct_name, f)
    needs_blank = False
    if needs_ctor(struct_name, hasid):
        f.write(decl.ctor % vars)
        needs_blank = True
    if struct_name in setup:
        write_setup(struct_name, f)
        needs_blank = True
    if needs_blank:
        f.write('\n')
    if hasid:
        f.write(decl.tmpl % dict(ftype = 'int', fname = 'ID'))
    for field in sfields[struct_name]:
        fname, issize, ftype, code, dfl, comment = field
        if not ftype:
            continue
        if issize:
            continue
        fvars = dict(
            ftype = cpp_type(ftype, False, struct_name),
            fname = fname)
        f.write(decl.tmpl % fvars)
    f.write(decl.footer % vars)

def generate_chunks(f, struct_name, vars):
    f.write(chunk.header % vars)
    mwidth = max(len(field[0] + ('_size' if field[1] else '')) for field in sfields[struct_name]) + 1
    mwidth = (mwidth + 3) // 4 * 4
    # print struct_name, mwidth
    sf = sfields[struct_name]
    n = len(sf)
    for i, field in enumerate(sf):
        fname, issize, ftype, code, dfl, comment = field
        if issize:
            fname += '_size'
        pad = mwidth - len(fname)
        ntabs = (pad + 3) // 4
        tabs = '\t' * ntabs
        comma = ' ' if i == n - 1 else ','
        fvars = dict(
            fname = fname,
            tabs = tabs,
            code = code,
            comma = comma,
            comment = comment)
        f.write(chunk.tmpl % fvars)
    f.write(chunk.footer % vars)

def generate_struct(filetype, filename, struct_name, hasid):
    if struct_name not in sfields:
        return

    vars = dict(
        filetype = filetype,
        filename = filename,
        typeupper = filetype.upper(),
        structname = struct_name,
        structupper = struct_name.upper(),
        idtype = ['NoID','WithID'][hasid])

    filepath = os.path.join(srcdir, '%s_%s.cpp' % (filetype, filename))
    with open(filepath, 'w') as f:
        generate_reader(f, struct_name, vars)

    if needs_ctor(struct_name, hasid) or needs_enums(struct_name):
        filepath = os.path.join(srcdir, 'rpg_%s.cpp' % filename)
        with open(filepath, 'w') as f:
            if needs_ctor(struct_name, hasid):
                generate_ctor(f, struct_name, hasid, vars)
            if needs_enums(struct_name):
                generate_enums(f, struct_name)

    filepath = os.path.join(hdrdir, 'rpg_%s.h' % filename)
    with open(filepath, 'w') as f:
        generate_header(f, struct_name, hasid, vars)

    filepath = os.path.join(hdrdir, '%s_chunks.h' % filetype)
    with open(filepath, 'a') as f:
        generate_chunks(f, struct_name, vars)

def generate_rawstruct(filename, struct_name):
    vars = dict(
        filename = filename,
        structname = struct_name,
        structupper = struct_name.upper())

    if needs_ctor(struct_name, False) or needs_enums(struct_name):
        filepath = os.path.join(srcdir, 'rpg_%s.cpp' % filename)
        with open(filepath, 'w') as f:
            if needs_ctor(struct_name, False):
                generate_ctor(f, struct_name, False, vars)
            if needs_enums(struct_name):
                generate_enums(f, struct_name)

    filepath = os.path.join(hdrdir, 'rpg_%s.h' % filename)
    with open(filepath, 'w') as f:
        generate_header(f, struct_name, False, vars)

def generate_flags(filetype, filename, struct_name):
    maxsize = (len(flags[struct_name]) + 7) // 8
    maxwidth = max(len(fname) for fname in flags[struct_name])
    maxwidth = (maxwidth + 2 + 3) // 4 * 4
    vars = dict(
        filetype = filetype,
        filename = filename,
        structname = struct_name,
        structupper = struct_name.upper(),
        maxsize = maxsize
        )

    filepath = os.path.join(srcdir, '%s_%s_flags.cpp' % (filetype, filename))
    with open(filepath, 'w') as f:
        f.write(copy.header)
        f.write(freader.header % vars)
        for fname in flags[struct_name]:
            width = len(fname)
            pad1 = maxwidth - width - 2
            tabs1 = (pad1 + 3) // 4
            pad2 = maxwidth - width - 2
            tabs2 = (pad2 + 3) // 4
            fvars = dict(
                fname = fname,
                pad1 = '\t' * tabs1,
                pad2 = '\t' * tabs2)
            f.write(freader.tmpl % fvars)
        f.write(freader.footer % vars)

def generate():
    for filetype in ['ldb','lmt','lmu','lsd']:
        vars = dict(
            filetype = filetype,
            typeupper = filetype.upper())
        filepath = os.path.join(hdrdir, '%s_chunks.h' % filetype)
        with open(filepath, 'w') as f:
            f.write(copy.header)
            f.write(chunk.file_header % vars)

    for filetype, filename, struct_name, hasid in structs:
        if hasid is not None:
            generate_struct(filetype, filename, struct_name, hasid)
        else:
            generate_rawstruct(filename, struct_name)
        if struct_name in flags:
            generate_flags(filetype, filename, struct_name)

    for filetype in ['ldb','lmt','lmu','lsd']:
        filepath = os.path.join(hdrdir, '%s_chunks.h' % filetype)
        with open(filepath, 'a') as f:
            f.write(chunk.file_footer)

def list_files_struct(filetype, filename, struct_name, hasid):
    if struct_name not in sfields:
        return
    print('%s_%s.cpp' % (filetype, filename))
    if needs_ctor(struct_name, hasid):
        print('rpg_%s.cpp' % filename)
    print('rpg_%s.h' % filename)

def list_files_rawstruct(filename, struct_name):
    if needs_ctor(struct_name, False):
        print('rpg_%s.cpp' % filename)
    print('rpg_%s.h' % filename)

def list_files_flags(filetype, filename, struct_name):
    print('%s_%s_flags.cpp' % (filetype, filename))

def list_files():
    for filetype in ['ldb','lmt','lmu','lsd']:
        print('%s_chunks.h' % filetype)

    for filetype, filename, struct_name, hasid in structs:
        if hasid is not None:
            list_files_struct(filetype, filename, struct_name, hasid)
        else:
            list_files_rawstruct(filename, struct_name)
        if struct_name in flags:
            list_files_flags(filetype, filename, struct_name)

def differ(srcfile, dstfile):
    with open(srcfile,'r') as f:
        src = f.read()
    with open(dstfile,'r') as f:
        dst = f.read()
    return src != dst

def update():
    if not os.path.exists(dstdir):
        os.mkdir(dstdir)

    for file in os.listdir(srcdir):
        srcfile = os.path.join(srcdir, file)
        dstfile = os.path.join(dstdir, file)
        if (not os.path.exists(dstfile) or
            os.path.getsize(srcfile) != os.path.getsize(dstfile) or
            differ(srcfile, dstfile)):
            os.remove(dstfile)
            os.rename(srcfile, dstfile)
        else:
            os.remove(srcfile)

def main(argv):
    global structs, sfields, enums, efields, flags, setup, headers

    structs = get_structs()
    sfields = get_fields()
    enums, efields = get_enums()
    flags = get_flags()
    setup = get_setup()
    headers = get_headers(structs, sfields, setup)

    if argv[1:] == ['-l']:
        list_files()
    else:
        if not os.path.exists(srcdir):
            os.mkdir(srcdir)
        generate()
        update()
        os.rmdir(srcdir)

if __name__ == '__main__':
    main(sys.argv)
