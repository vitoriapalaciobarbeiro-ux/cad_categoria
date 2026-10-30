from flask import Flask, render_template, request, flash, redirect, url_for, session, send_file
import fdb
from flask_bcrypt import Bcrypt
from datetime import date

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.config['SECRET_KEY'] = 'Meu-salario'

# conectar o banco:
host = 'localhost'
database = r'C:\Users\rehme\OneDrive\Ambiente de Trabalho\SPRINT03.FDB'
user = 'sysdba'
password = 'sysdba'

con = fdb.connect(host=host, database=database, user=user, password=password, )  # conectar o banco


@app.route('/')
def index():
    return render_template('index.html')


def validar_senha(senha):
    if len(senha) < 8:
        return False
    tem_maiusculo = False
    tem_minusculo = False
    tem_numero = False

    for caractere in senha:
        if caractere.isupper():
            tem_maiusculo = True

        if caractere.islower():
            tem_minusculo = True

        if caractere.isdigit():
            tem_numero = True

    if tem_maiusculo == False:
        return False

    if tem_minusculo == False:
        return False

    if tem_numero == False:
        return False

    return True


# CADASTRAR
@app.route('/cadastro')
def cadastro():
    return render_template('cadastro.html')


@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    nome = request.form['nome']
    cpf = request.form['cpf']
    telefone = request.form['telefone']
    email = request.form['email']
    senha = request.form['senha']
    confirmar = request.form['confirmar']

    if not validar_senha(senha):
        flash('Senha fraca!')
        return redirect(url_for('cadastro'))

    senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')
    cursor = con.cursor()

    if senha != confirmar:
        flash('As senhas não são iguais!')
        return redirect(url_for('cadastro'))

    if nome.strip() and email.strip() and telefone.strip() and cpf.strip() == "":
        flash('Não podem ter campos vazios!')
        return redirect(url_for('cadastro'))

    else:
        try:
            cursor.execute(""" SELECT 1
                              FROM usuario
                              WHERE email = ? OR TELEFONE = ? OR CPF = ?""", (email, telefone, cpf))
            if cursor.fetchone() is not None:
                flash("Erro: Usuário já cadastrado!")
                return redirect(url_for('cadastro'))

            cursor.execute("""INSERT INTO usuario (nome, email, cpf, telefone, senha, valor_diario_padrao, valor_diario_excepcional, valor_pacotes, min_pacotes, min_trabalhadores)
                                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (nome, email, cpf, telefone, senha_hash, 0, 0, 0, 0, 0))
            con.commit()
            flash('Usuário cadastrado com sucesso!')

        except Exception as e:
            flash(f"Ocorreu um erro! -> {e}")
            con.rollback()

        finally:
            cursor.close()

        return redirect(url_for('login'))


# LOGIN
@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/entrar', methods=['GET', 'POST'])
def entrar():
    if request.method == 'POST':
        login = request.form['login']
        senha = request.form['senha']

        cursor = con.cursor()
        try:
            cursor.execute("""SELECT ID_USUARIO, SENHA, TENTATIVA, STATUS, NOME FROM USUARIO WHERE EMAIL = ?""",
                           (login,))
            usuario = cursor.fetchone()
            if not usuario:  # seleciona um único valor
                flash('Usuário não encontrado!')
                return redirect(url_for('login'))

            id_usuario, senha_hash, tentativa, status, nome = usuario

            if status == 0:
                if usuario:
                    if bcrypt.check_password_hash(senha_hash, senha):
                        session['id_usuario'] = id_usuario
                        session['nome'] = nome

                        flash('Login bem-sucedido!')
                        tentativas = 0
                        cursor.execute('update usuario set tentativa = ? where id_usuario = ?',
                                       (tentativas, id_usuario))
                        con.commit()

                        return redirect(url_for('dashboard'))

                    else:
                        tentativa += 1
                        cursor.execute('update usuario set tentativa = ? where id_usuario = ?', (tentativa, id_usuario))
                        con.commit()

                        if tentativa == 3:
                            cursor.execute('update usuario set status = 1 where id_usuario = ?', (id_usuario,))
                            con.commit()
                            flash('Usuário está bloqueado , entre em contato com o administrador do sistema!')
                            return redirect(url_for('login'))

                        flash(f'Email ou senha inválidos!')
                        return redirect(url_for('login'))

                else:
                    return render_template('login.html')
            else:
                flash('Usuário Inativo!')
                return render_template('login.html')




        except Exception as e:

            print("ERRO ORIGINAL:", repr(e))

            flash(f'Ocorreu um erro -> {e}')

            return redirect(url_for('login'))

        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception as erro:
                    print("ERRO AO FECHAR CURSOR:", repr(erro))


@app.route('/logout')
def logout():
    session.pop('id_usuario', None)
    flash('Logout com sucesso!')
    return redirect(url_for('login'))


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))
    else:
        receitas = calcular_receitas()
        despesas = calcular_despesas()
        saldo = calcular_saldo()
        id_usuario = session['id_usuario']
        caminho = "img/capas/" + str(id_usuario) + ".jpg"
        return render_template('dashboard.html', nome=session['nome'], receitas=receitas, despesas=despesas, saldo=saldo, img=caminho)


def buscarUsuario(id):
    id = session['id_usuario']

    cursor = con.cursor()
    cursor.execute("""SELECT ID_USUARIO, NOME, email, senha, VALOR_DIARIO_PADRAO, VALOR_DIARIO_EXCEPCIONAL, VALOR_PACOTES, MIN_PACOTES, MIN_TRABALHADORES, CPF, TELEFONE
                             FROM USUARIO
                             WHERE id_usuario = ?""", (id,))
    usuario = cursor.fetchone()
    cursor.close()

    return usuario


@app.route('/editar_usuario')
def editar_usuario():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))

    else:
        cursor = con.cursor()

        cursor.execute("""SELECT ID_USUARIO, NOME, email, senha, VALOR_DIARIO_PADRAO, VALOR_DIARIO_EXCEPCIONAL, VALOR_PACOTES, MIN_PACOTES, MIN_TRABALHADORES, CPF, TELEFONE
                                FROM USUARIO
                                WHERE id_usuario = ?""", (session['id_usuario'],))
        usuario = cursor.fetchone()

        cursor.close()

        caminho = "img/capas/" + str(usuario[0]) + ".jpg"


        return render_template('editar_usuario.html', usuario=usuario, nome=usuario[1], img=caminho)


@app.route('/editar', methods=['GET', 'POST'])
def editar():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))

    else:
        cursor = con.cursor()

        try:
            id = session['id_usuario']

            usuario = buscarUsuario(session['id_usuario'])

            print(request.method)

            if request.method == 'POST':
                nome = request.form['nome']
                email = request.form['email']
                cpf = request.form['cpf']
                telefone = request.form['telefone']
                valor_padrao = float(request.form['valor_padrao'])
                valor_excepcional = float(request.form['valor_excepcional'])
                valor_pacotes = float(request.form['valor_pacotes'])
                min_pacotes = int(request.form['min_pacotes'])
                min_trabalhadores = int(request.form['min_trabalhadores'])
                arquivo = request.files['imagem']

                cursor.execute("""SELECT 1
                                     FROM usuario
                                     WHERE (email = ? 
                                     OR TELEFONE = ? 
                                     OR CPF = ?) 
                                     AND id_usuario != ?""",
                               (email, telefone, cpf, session['id_usuario']))

                if cursor.fetchone() is not None:
                    flash("Erro: Usuário já cadastrado!")
                    return redirect(url_for('editar'))

                if nome.strip() and email.strip() and cpf.strip() and telefone.strip() != "":

                    cursor.execute("""UPDATE USUARIO
                                       SET NOME = ?,
                                       EMAIL = ?,
                                       CPF = ?,
                                       TELEFONE = ?,
                                       VALOR_DIARIO_PADRAO = ?,
                                       VALOR_DIARIO_EXCEPCIONAL = ?,
                                       VALOR_PACOTES = ?,
                                       MIN_PACOTES = ?,
                                       MIN_TRABALHADORES = ?
                                       WHERE ID_USUARIO = ?""",
                                   (nome, email, cpf, telefone, valor_padrao, valor_excepcional, valor_pacotes, min_pacotes, min_trabalhadores, id))
                    con.commit()

                    arquivo.save(f'static/img/capas/{id}.jpg')

                    flash("Usuário editado com sucesso!")

                    usuario = buscarUsuario(id)

                else:
                    flash('Não podem existir campos nulos!')
        except Exception as e:
            print(e)
            flash(f"Ocorreu um erro! -> {e}")

        finally:
            caminho = "img/capas/" + str(usuario[0]) + ".jpg"
            return render_template('editar_usuario.html', nome=usuario[1], usuario=usuario, img=caminho)


def senhas_anteriores(senha_modificada):
    cursor = con.cursor()
    id_usuario = session['id_usuario']

    cursor.execute("""SELECT SENHA, SENHA1, SENHA2 FROM USUARIO WHERE ID_USUARIO = ?""", (id_usuario,))
    senha_atual, senha1, senha2 = cursor.fetchone()

    if (bcrypt.check_password_hash(senha_atual, senha_modificada) or
            (senha1 and bcrypt.check_password_hash(senha1, senha_modificada)) or
            (senha2 and bcrypt.check_password_hash(senha2, senha_modificada))):
        return False
    else:
        alt_senha2 = senha_atual
        alt_senha1 = senha2
        alt_senha = bcrypt.generate_password_hash(senha_modificada).decode('utf-8')

        print(alt_senha, alt_senha1, alt_senha2)

        cursor.execute("""UPDATE USUARIO SET SENHA = ?, SENHA1 = ?, SENHA2 = ? WHERE ID_USUARIO = ?""",
                       (alt_senha, alt_senha1, alt_senha2, id_usuario))
        cursor.close()

        return True


@app.route('/editar_senha')
def editar_senha():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))
    else:
        nome = buscarUsuario(id)[1]
        return render_template('editar_senha.html', nome=nome)


@app.route('/senha', methods=['GET', 'POST'])
def senha():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))


    else:
        cursor = con.cursor()
        try:
            id = session['id_usuario']
            usuario = buscarUsuario(id)
            print("ID:", id)
            print("USUARIO:", usuario)
            print("TIPO:", type(usuario))

            if request.method == 'POST':
                senha_atual = request.form['senha_atual']
                nova_senha = request.form['nova_senha']
                confirma_senha = request.form['confirma_senha']

                if bcrypt.check_password_hash(usuario[3], senha_atual):
                    if nova_senha == confirma_senha:
                        if validar_senha(nova_senha):
                            if senhas_anteriores(nova_senha):
                                flash("Senha alterada com sucesso!")
                            else:
                                flash("A senha tem que ser diferente das anteriores!")
                        else:
                            flash("Informe uma senha segura!")
                    else:
                        flash("As senhas não são iguais!")
                else:
                    flash("Senha incorreta!")


        except Exception as e:
            print(e)
            flash(f"Ocorreu um erro! -> {e}")

        finally:
            cursor.close()

        nome = usuario[1]
        return render_template('editar_usuario.html', usuario=usuario, nome=nome)


@app.route('/categorias')
def categorias():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))
    else:
        resultado = buscarCategorias(session['id_usuario'])

        if not resultado:
            id = None
        else:
            id = resultado[0][0]

        return render_template('cad_categorias.html', nome=session['nome'], id=id)




@app.route('/cadcategorias', methods=['POST'])
def cadcategorias():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))

    else:
        cursor = con.cursor()
        nome_categoria = request.form['nome_categoria'].lower()
        cor = request.form['cor']
        icone = request.form['icone']

        buscarCategorias(session['id_usuario'])

        if nome_categoria.strip() == "":
            flash('Preencha o campo para cadastrar!')
            return redirect(url_for('categorias'))

        cursor.execute("""SELECT 1
                          FROM CATEGORIA
                          WHERE LOWER(NOME) = ? AND COR = ?""",
                       (nome_categoria, cor))

        if cursor.fetchone() is not None:
            flash("Erro: Categoria já cadastrada!")
            return redirect(url_for('categorias'))

        else:
            id = session['id_usuario']

            try:
                cursor.execute("""INSERT INTO CATEGORIA
                                  (NOME, STATUS, ID_USUARIO, COR, ICONE)
                                  VALUES (?, ?, ?, ?, ?)""",
                               (nome_categoria, 0, id, cor, icone))

                con.commit()
                flash('Categoria cadastrada com sucesso!')

            except Exception as e:
                flash(f"Ocorreu um erro! -> {e}")
                con.rollback()

            finally:
                cursor.close()

            return redirect(url_for('categorias'))



def buscarCategorias(id):
    id = session['id_usuario']

    cursor = con.cursor()
    cursor.execute("""SELECT ID_CATEGORIA, NOME, STATUS
                             FROM CATEGORIA
                             WHERE id_usuario = ?""", (id,))
    categorias = cursor.fetchall()
    cursor.close()
    if not categorias:
        categorias = ''

    return categorias


@app.route('/movimentacoes')
def movimentacoes():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))
    else:
        id = session['id_usuario']
        data = date.today()
        print(id)
        categorias = buscarCategorias(id)
        print(categorias)
        usuario = buscarUsuario(id)
        caminho = "img/capas/" + str(usuario[0]) + ".jpg"
        return render_template('cad_movimentacoes.html', nome=session['nome'], categorias=categorias, data=data, img=caminho)


@app.route('/cadmovimentacoes', methods=['POST'])
def cadmovimentacoes():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))
    else:
        id = session['id_usuario']
        cursor = con.cursor()
        tipo = request.form['tipo']
        print(tipo)
        categoria = request.form['categoria']
        data = date.today()
        descricao = request.form['descricao']
        valor = request.form['valor']

        try:
            cursor.execute("""INSERT INTO movimentacao (id_usuario, tipo, id_categoria, data_movimentacao, descricao, valor_total, status)
                                          values (?,?,?,?,?,?,?)""", (id, tipo, categoria, data, descricao, valor, 0))
            con.commit()
            flash('Movimentação cadastrada com sucesso!')

        except Exception as e:
            flash(f"Ocorreu um erro! -> {e}")
            con.rollback()

        finally:
            cursor.close()

        return redirect(url_for('historico_movimentacoes'))  # mudar para colocar editar

@app.route('/historico_movimentacoes', methods=['GET', 'POST'])
def historico_movimentacoes():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))

    else:
        banco = """SELECT M.DATA_MOVIMENTACAO
                           , CASE M.TIPO
                                WHEN 1 THEN 'Despesa'
                                WHEN 0 THEN 'Receita'
                                ELSE ''
                             END AS tipo
                           , c.nome nome_categoria
                           , M.DESCRICAO
                           , M.VALOR_TOTAL
                           , M.STATUS
                           , M.ID_MOVIMENTACAO
                    FROM MOVIMENTACAO m
                    LEFT JOIN CATEGORIA c ON c.id_categoria = m.ID_CATEGORIA
                    WHERE m.ID_USUARIO = ?"""

        parametros = [session['id_usuario']]

        if request.method == 'POST':
            tipo = request.form['tipo']
            descricao = request.form['descricao'].lower()
            categoria = request.form['categoria']
            data_inicial = request.form['data_inicial']
            data_final = request.form['data_final']

            if descricao:
                banco += ' AND lower(m.descricao) LIKE ? '
                parametros.append(f'%{descricao}%')

            if tipo:
                banco += ' AND m.tipo = ? '
                parametros.append(tipo)

            if categoria:
                banco += ' AND m.id_categoria = ? '
                parametros.append(categoria)

            if data_inicial and data_final:
                banco += ' AND m.data_movimentacao BETWEEN ? AND ? '
                parametros.append(data_inicial)
                parametros.append(data_final)

        cursor = con.cursor()
        cursor.execute(banco, parametros)

        movimentacoes = cursor.fetchall()
        cursor.close()
        print(movimentacoes)

        data = date.today()
        categorias = buscarCategorias(session['id_usuario'])


        usuario = buscarUsuario(id)
        caminho = "img/capas/" + str(usuario[0]) + ".jpg"

        return (render_template(
            'historico_movimentacoes.html',
            movimentacoes=movimentacoes,
            data=data,
            nome=session['nome'],
            categorias=categorias,
            img=caminho
        ))

@app.route('/excluir_movimentacao/<int:id>', methods=['POST'])
def excluir_movimentacao(id):
    if 'id_usuario' not in session:
        flash('Precisa estar logado')
        return redirect(url_for('login'))
    else:
        cursor = con.cursor()

        try:
            cursor.execute("""
                DELETE FROM MOVIMENTACAO
                WHERE ID_MOVIMENTACAO = ?
                AND ID_USUARIO = ?
            """, (id, session['id_usuario']))

            con.commit()
            flash('Movimentação deletado com sucesso!')
            return redirect(url_for('historico_movimentacoes'))

        except Exception as e:
            con.rollback()
            flash(f'Ocorreu um erro -> {e}')
            return redirect(url_for('historico_movimentacoes'))

        finally:
            cursor.close()


def calcula_valor_dia(qtd_trabalhadores, vn_PACOTES_COLETADOS):
    id_usuario = session['id_usuario']
    cursor = None

    try:
        cursor = con.cursor()
        cursor.execute('''
           SELECT
               u.VALOR_DIARIO_PADRAO,
               u.VALOR_DIARIO_EXCEPCIONAL,
               u.VALOR_PACOTES,
               u.MIN_PACOTES,
               u.MIN_TRABALHADORES
           FROM USUARIO u
           WHERE u.id_usuario = ?
       ''', (id_usuario,))

        usuario = cursor.fetchone()

        vn_valor_diario_padrao, vn_valor_diario_excepcional, vn_valor_pacotes, vn_min_pacotes, vn_min_trabalhadores = usuario

        if qtd_trabalhadores <= int(vn_min_trabalhadores):
            if vn_min_pacotes < vn_PACOTES_COLETADOS:
                vn_valor_dia_total = (
                        vn_valor_pacotes * vn_PACOTES_COLETADOS
                        + vn_valor_diario_excepcional
                )
            else:
                vn_valor_dia_total = (
                    vn_valor_diario_excepcional
                )
        else:
            if vn_min_pacotes < vn_PACOTES_COLETADOS:
                vn_valor_dia_total = (
                        vn_valor_pacotes * vn_PACOTES_COLETADOS
                        + vn_valor_diario_padrao
                )
            else:
                vn_valor_dia_total = (
                    vn_valor_diario_padrao
                )

        return vn_valor_dia_total

    except Exception as e:
        flash(f'Deu erro {e}')
        return None


    finally:
        if cursor is not None:
            cursor.close()


# TUDO RELACIONADO AO TRABALHO DIÁRIO:
@app.route('/trabalho_diario')
def trabalho_diario():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))
    else:
        nome = buscarUsuario(id)[1]
        data = date.today()
        usuario = buscarUsuario(id)
        caminho = "img/capas/" + str(usuario[0]) + ".jpg"
        return render_template('trabalho_diario.html', nome=nome, data=data, img=caminho)


@app.route('/adicionar_trabalho', methods=['GET', 'POST'])
def adicionar_trabalho():
    cursor = None
    try:
        if request.method == 'POST':
            id = session['id_usuario']
            pacotes = request.form['pacotes']
            trabalhadores = request.form['trabalhadores']
            data = date.today()

            if pacotes.strip() != "" and trabalhadores.strip() != "":
                valor_dia_total = calcula_valor_dia(
                    int(trabalhadores), int(pacotes)
                )

                cursor = con.cursor()
                cursor.execute("""
                   INSERT INTO servico_diario (
                       PACOTES_COLETADOS,
                       QTD_TRABALHADORES,
                       DATA_SERVICO_DIARIO,
                       id_usuario,
                       VALOR_DIA_TOTAL,
                       STATUS
                   )
                   VALUES (?, ?, ?, ?, ?, ?)
               """, (pacotes, trabalhadores, data, id, valor_dia_total, 0))

                con.commit()
                flash("Serviço diário cadastrado com sucesso!")
                return redirect(url_for('historico_trabalho'))

            else:
                flash("Não podem existir campos nulos!")
                return redirect(url_for('trabalho_diario'))

    except Exception as e:
        print(e)
        flash(f"Ocorreu um erro! -> {e}")
        return redirect(url_for('trabalho_diario'))
    finally:
        if cursor is not None:
            cursor.close()
    return render_template('historico_trabalho.html')


@app.route('/historico_trabalho', methods=['GET', 'POST'])
def historico_trabalho():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))

    else:
        banco = """SELECT sd.DATA_SERVICO_DIARIO 
                     ,sd.PACOTES_COLETADOS 
                     ,sd.QTD_TRABALHADORES 
                     ,sd.VALOR_DIA_TOTAL 
                     ,sd.ID_SERVICO_DIARIO
                     ,sd.STATUS
                    FROM SERVICO_DIARIO sd
                    WHERE SD.ID_USUARIO = ?"""

        parametros = [session['id_usuario']]

        if request.method == 'POST':
            data_inicial = request.form['data_inicial']
            data_final = request.form['data_final']

            if data_inicial and data_final:
                banco += ' AND data_servico_diario BETWEEN ? AND ? '
                parametros.append(data_inicial)
                parametros.append(data_final)

        cursor = con.cursor()
        cursor.execute(banco, parametros)

        trabalhos = cursor.fetchall()
        cursor.close()

        nome = buscarUsuario(id)[1]
        data = date.today()
        usuario = buscarUsuario(id)
        caminho = "img/capas/" + str(usuario[0]) + ".jpg"
        return render_template('historico_trabalho.html', trabalhos=trabalhos, data=data, nome=nome, img=caminho)


@app.route('/editar_trabalho/<int:id>', methods=['GET', 'POST'])
def editar_trabalho(id):
    cursor = con.cursor()
    nome = buscarUsuario(id)[1]

    try:
        cursor.execute("""
            SELECT
                DATA_SERVICO_DIARIO,
                PACOTES_COLETADOS,
                QTD_TRABALHADORES
            FROM SERVICO_DIARIO
            WHERE ID_SERVICO_DIARIO = ?
        """, (id,))

        servico = cursor.fetchone()

        if servico is None:
            flash("Registro de trabalho NÃO encontrado")
            return redirect(url_for('historico_trabalho'))

        if request.method == 'POST':
            pacotes = int(request.form['pacotes'])
            trabalhadores = int(request.form['trabalhadores'])

            valor_dia_total = calcula_valor_dia(trabalhadores, pacotes)

            cursor.execute("""
                UPDATE SERVICO_DIARIO
                SET PACOTES_COLETADOS = ?,
                    QTD_TRABALHADORES = ?,
                    VALOR_DIA_TOTAL = ?
                WHERE ID_SERVICO_DIARIO = ?
            """, (pacotes, trabalhadores, valor_dia_total, id))

            con.commit()

            flash("Registro de trabalho editado com sucesso!")
            return redirect(url_for('historico_trabalho'))

        usuario = buscarUsuario(id)
        caminho = "img/capas/" + str(usuario[0]) + ".jpg"

        return render_template(
            'editar_trabalho.html',
            servico=servico,
            id=id,
            nome=nome,
            img=caminho
        )

    except Exception as e:
        con.rollback()
        flash(f"Ocorreu um erro! -> {e}")
        return redirect(url_for('historico_trabalho'))

    finally:
        cursor.close()


@app.route('/excluir_trabalho/<int:id>', methods=['POST'])
def excluir_trabalho(id):
    if 'id_usuario' not in session:
        flash('Precisa estar logado')
        return redirect(url_for('login'))
    else:
        cursor = con.cursor()

        try:
            cursor.execute("""
                DELETE FROM MOVIMENTACAO
                WHERE ID_SERVICO_DIARIO = ?
            """, (id,))

            cursor.execute("""
                DELETE FROM SERVICO_DIARIO
                WHERE ID_SERVICO_DIARIO = ?
                AND ID_USUARIO = ?
            """, (id, session['id_usuario']))

            con.commit()
            flash('Serviço diário deletado com sucesso!')
            return redirect(url_for('historico_trabalho'))

        except Exception as e:
            con.rollback()
            flash(f'Ocorreu um erro -> {e}')
            return redirect(url_for('historico_trabalho'))

        finally:
            cursor.close()


# TUDO RELACIONADO A SERVIÇO EXTRA
@app.route('/servico_extra')
def servico_extra():
    if 'id_usuario' not in session:
        flash('Precisa estar loggado')
        return redirect(url_for('login'))
    else:
        nome = buscarUsuario(id)[1]
        data = date.today()
        usuario = buscarUsuario(id)
        caminho = "img/capas/" + str(usuario[0]) + ".jpg"
        return render_template('servico_extra.html', nome=nome, data=data, img=caminho)


@app.route('/cadastrar_servico', methods=['GET', 'POST'])
def cadastrar_servico():
    try:
        if request.method == 'POST':
            id = session['id_usuario']
            servico = request.form['servico']
            valor = request.form['valor']
            data = date.today()
            cursor = con.cursor()
            if valor.strip() and servico.strip() != "":
                cursor.execute("""INSERT INTO SERVICO_EXTRA (servico,DATA_SERVICO_EXTRA,
                                           VALOR_RECEBIDO, id_usuario, status) values(?,?,?,?,?)""",
                               (servico, data, valor, id, 0))
                con.commit()

                flash("Serviço extra cadastrado com sucesso!")

            else:
                flash('Não podem existir campos nulos!')

    except Exception as e:
        print(e)
        flash(f"Ocorreu um erro! -> {e}")

    finally:
        return redirect(url_for('historico_servico_extra'))

@app.route('/excluir_servico_extra/<int:id>', methods=['POST'])
def excluir_servico_extra(id):
    if 'id_usuario' not in session:
        flash('Precisa estar logado')
        return redirect(url_for('login'))
    else:
        cursor = con.cursor()

        try:
            cursor.execute("""
                DELETE FROM MOVIMENTACAO
                WHERE ID_SERVICO_EXTRA = ?
            """, (id,))

            cursor.execute("""
                DELETE FROM SERVICO_EXTRA
                WHERE ID_SERVICO_EXTRA = ?
                AND ID_USUARIO = ?
            """, (id, session['id_usuario']))

            con.commit()
            flash('Serviço diário deletado com sucesso!')
            return redirect(url_for('historico_servico_extra'))

        except Exception as e:
            con.rollback()
            flash(f'Ocorreu um erro -> {e}')
            return redirect(url_for('historico_servico_extra'))

        finally:
            cursor.close()

@app.route('/alterar_status_extra/<int:id>', methods=['POST'])
def alterar_status_extra(id):
    if 'id_usuario' not in session:
        flash('Precisa estar logado')
        return redirect(url_for('login'))

    else:
        cursor = con.cursor()
        cursor.execute("""SELECT STATUS FROM SERVICO_EXTRA WHERE ID_SERVICO_EXTRA = ? AND ID_USUARIO = ?""", (id, session['id_usuario']))
        status = cursor.fetchone()[0]
        print(status)

        try:

            if status == 0:
                cursor.execute("""UPDATE SERVICO_EXTRA SET STATUS = 1 WHERE ID_SERVICO_EXTRA = ?""", (id,))
                con.commit()
                flash('Status alterado com sucesso!')

            elif status == 1:
                cursor.execute("""UPDATE SERVICO_EXTRA SET STATUS = 0 WHERE ID_SERVICO_EXTRA = ?""", (id,))
                con.commit()
                flash('Status alterado com sucesso!')

            return redirect(url_for('historico_servico_extra'))

        except Exception as e:
            con.rollback()
            flash(f'Ocorreu um erro -> {e}')
            return redirect(url_for('historico_servico_extra'))

        finally:
            cursor.close()



@app.route('/alterar_status_movimentacao/<int:id>', methods=['POST'])
def alterar_status_movimentacao(id):
    print('entrei')
    if 'id_usuario' not in session:
        flash('Precisa estar logado')
        return redirect(url_for('login'))

    else:
        print('2')
        cursor = con.cursor()
        cursor.execute("""SELECT STATUS FROM MOVIMENTACAO WHERE ID_MOVIMENTACAO = ? AND ID_USUARIO = ?""", (id, session['id_usuario']))
        status = cursor.fetchone()[0]
        print(status)

        try:

            if status == 0:
                print('3')
                cursor.execute("""UPDATE MOVIMENTACAO SET STATUS = 1 WHERE ID_MOVIMENTACAO = ?""", (id,))
                con.commit()
                flash('Status alterado com sucesso!')

            elif status == 1:
                print('4')
                cursor.execute("""UPDATE MOVIMENTACAO SET STATUS = 0 WHERE ID_MOVIMENTACAO = ?""", (id,))
                con.commit()
                flash('Status alterado com sucesso!')

            print('5')
            return redirect(url_for('historico_movimentacoes'))

        except Exception as e:
            con.rollback()
            flash(f'Ocorreu um erro -> {e}')
            return redirect(url_for('historico_movimentacoes'))

        finally:
            cursor.close()

@app.route('/alterar_status_trabalho/<int:id>', methods=['POST'])
def alterar_status_trabalho(id):
    if 'id_usuario' not in session:
        flash('Precisa estar logado')
        return redirect(url_for('login'))

    else:
        cursor = con.cursor()
        cursor.execute("""SELECT STATUS FROM SERVICO_DIARIO WHERE ID_SERVICO_DIARIO = ? AND ID_USUARIO = ?""", (id, session['id_usuario']))
        status = cursor.fetchone()[0]

        try:

            if status == 0:
                cursor.execute("""UPDATE SERVICO_DIARIO SET STATUS = 1 WHERE ID_SERVICO_DIARIO = ?""", (id,))
                con.commit()
                flash('Status alterado com sucesso!')

            elif status == 1:
                cursor.execute("""UPDATE SERVICO_DIARIO SET STATUS = 0 WHERE ID_SERVICO_DIARIO = ?""", (id,))
                con.commit()
                flash('Status alterado com sucesso!')

            return redirect(url_for('historico_trabalho'))

        except Exception as e:
            con.rollback()
            flash(f'Ocorreu um erro -> {e}')
            return redirect(url_for('historico_trabalho'))

        finally:
            cursor.close()

@app.route('/historico_servico_extra', methods=['GET', 'POST'])
def historico_servico_extra():
    if 'id_usuario' not in session:
        flash('Precisa estar logado')
        return redirect(url_for('login'))

    banco = """SELECT
                se.ID_SERVICO_EXTRA,
                se.ID_USUARIO,
                se.DATA_SERVICO_EXTRA,
                se.SERVICO,
                se.VALOR_RECEBIDO,
                se.STATUS
            FROM SERVICO_EXTRA se
            WHERE se.ID_USUARIO = ?"""

    parametros = [session['id_usuario']]

    if request.method == 'POST':

        status = request.form['status']
        data_inicial = request.form['data_inicial']
        data_final = request.form['data_final']

        if status:
            banco += ' AND se.status = ? '
            parametros.append(status)

        if data_inicial and data_final:
            banco += ' AND se.data_servico_extra BETWEEN ? AND ? '
            parametros.append(data_inicial)
            parametros.append(data_final)

    cursor = con.cursor()

    try:
        cursor.execute(banco, parametros)

        servicos = cursor.fetchall()

        nome = buscarUsuario(session['id_usuario'])[1]
        data = date.today()
        usuario = buscarUsuario(id)
        caminho = "img/capas/" + str(usuario[0]) + ".jpg"

        return render_template(
                                'historico_servico_extra.html',
                                servicos=servicos,
                                data=data,
                                nome=nome,
                                img=caminho)

    except Exception as e:
        con.rollback()
        flash(f'Ocorreu um erro -> {e}')
        return redirect(url_for('historico_servico_extra'))

    finally:
        cursor.close()

#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#ROTAS DE CÁLCULO AUTOMÁTICO DE SALDO
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
def calcular_receitas():
    cursor = con.cursor()
    try:
        cursor.execute("""
            SELECT cast(SUM(VALOR_TOTAL) as numeric(15,2))
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ?
            AND TIPO = 0
            AND STATUS = 0
        """, (session['id_usuario'],))

        receitas = cursor.fetchone()[0]

        if receitas is None:
            receitas = 0

        return receitas
    finally:
        cursor.close()


def calcular_despesas():
    cursor = con.cursor()

    try:
        # O CAST converte a soma para um número decimal com duas casas decimais.
        cursor.execute("""
            SELECT cast(SUM(VALOR_TOTAL) as numeric(15,2))
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ?
            AND TIPO = 1
            AND STATUS = 0
        """, (session['id_usuario'],))

        despesas = cursor.fetchone()[0]

        if despesas is None:
            despesas = 0

        return despesas
    finally:
        cursor.close()


def calcular_saldo():
    banco_receitas = """SELECT cast(SUM(VALOR_TOTAL) as numeric(15,2))
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                AND TIPO = 0
                AND STATUS = 0"""

    banco_despesas = """SELECT cast(SUM(VALOR_TOTAL) as numeric(15,2))
                    FROM MOVIMENTACAO
                    WHERE ID_USUARIO = ?
                    AND TIPO = 1
                    AND STATUS = 0"""

    parametros = [session['id_usuario']]

    if request.method == 'POST':
        data_inicial = request.form['data_inicial']
        data_final = request.form['data_final']

        if data_inicial and data_final:
            banco_despesas += ' AND data_movimentacao BETWEEN ? AND ? '
            banco_receitas += ' AND data_movimentacao BETWEEN ? AND ? '
            parametros.append(data_inicial)
            parametros.append(data_final)

    cursor = con.cursor()

    cursor.execute(banco_receitas,parametros)

    receitas = cursor.fetchone()[0]

    if receitas is None:
        receitas = 0

    cursor.execute(banco_despesas,parametros)

    despesas = cursor.fetchone()[0]

    if despesas is None:
        despesas = 0

    saldo = receitas - despesas
    cursor.close()
    return saldo

@app.route('/editar_servico_extra/<int:id>', methods=['GET', 'POST'])
def editar_servico_extra(id):
    if 'id_usuario' not in session:
        flash('Precisa estar logado')
        return redirect(url_for('login'))

    cursor = con.cursor()

    try:
        cursor.execute("""
            SELECT SERVICO, VALOR_RECEBIDO, DATA_SERVICO_EXTRA
            FROM SERVICO_EXTRA
            WHERE ID_SERVICO_EXTRA = ?
            AND ID_USUARIO = ?
        """, (id, session['id_usuario']))

        servico = cursor.fetchone()

        if servico is None:
            flash('Serviço extra não encontrado!')
            return redirect(url_for('historico_servico_extra'))

        if request.method == 'POST':
            nome_servico = request.form['servico'].strip()
            valor = float(request.form['valor'].replace(',', '.'))

            if not nome_servico or valor <= 0:
                flash('Informe um serviço e um valor válido!')
                return redirect(url_for('editar_servico_extra', id=id))

            cursor.execute("""
                UPDATE SERVICO_EXTRA
                SET SERVICO = ?, VALOR_RECEBIDO = ?
                WHERE ID_SERVICO_EXTRA = ?
                AND ID_USUARIO = ?
            """, (nome_servico, valor, id, session['id_usuario']))

            con.commit()
            flash('Serviço extra editado com sucesso!')
            return redirect(url_for('historico_servico_extra'))

        nome = buscarUsuario(session['id_usuario'])[1]
        usuario = buscarUsuario(id)
        caminho = "img/capas/" + str(usuario[0]) + ".jpg"

        return render_template(
            'editar_servico_extra.html',
            servico=servico,
            id=id,
            nome=nome,
            img=caminho
        )

    except Exception as e:
        con.rollback()
        flash(f'Ocorreu um erro: {e}')
        return redirect(url_for('historico_servico_extra'))

    finally:
        cursor.close()

@app.route('/editar_receita_e_depesa/<int:id>', methods=['GET', 'POST'])
def editar_receita_e_despesa(id):

    cursor = con.cursor()
    if 'id_usuario' not in session:
        flash('Precisa estar logado')
        return redirect(url_for('login'))

    nome = buscarUsuario(session['id_usuario'])[1]
    try:
        cursor.execute("""
            SELECT
                TIPO,
                ID_CATEGORIA,
                DESCRICAO,
                valor_total,
                data_movimentacao
            FROM MOVIMENTACAO
            WHERE ID_MOVIMENTACAO = ?
            and id_usuario = ?
        """, (id,session['id_usuario']))

        movimentacoes = cursor.fetchone()

        if movimentacoes is None:
            flash("Receita/Despesa NÃO encontrada")
            return redirect(url_for('historico_movimentacoes'))

        if request.method == 'POST':
            descricao = request.form['descricao']
            valor = float(request.form['valor'])
            categoria = int(request.form['categoria'])
            tipo = int(request.form['tipo'])

            cursor.execute("""
                UPDATE MOVIMENTACAO
                    SET DESCRICAO = ?,
                    id_CATEGORIA = ?,
                    tipo = ?,
                    valor_total = ?
                WHERE ID_movimentacao = ?
                and id_usuario = ?
            """, (descricao, categoria, tipo, valor, id, session['id_usuario']))

            con.commit()

            flash("Registro de receitas/trabalhos editado com sucesso!")
            return redirect(url_for('historico_movimentacoes'))

        categorias = buscarCategorias(session['id_usuario'])
        usuario = buscarUsuario(id)
        caminho = "img/capas/" + str(usuario[0]) + ".jpg"

        return render_template(
            'editar_movimentacoes.html',
            movimentacoes=movimentacoes,
            categorias=categorias,
            id=id,
            nome=nome,
            img=caminho
        )

    except Exception as e:
        con.rollback()
        flash(f"Ocorreu um erro! -> {e}")
        return redirect(url_for('historico_movimentacoes'))

    finally:
        cursor.close()


@app.route('/editar_categorias/<int:id>', methods=['GET', 'POST'])
def editar_categorias(id):
   if 'id_usuario' not in session:
       flash('Precisa estar logado')
       return redirect(url_for('login'))

   cursor = con.cursor()

   try:
       cursor.execute("""
           SELECT NOME, STATUS
           FROM CATEGORIA
           WHERE ID_CATEGORIA = ?
             AND ID_USUARIO = ?
       """, (id, session['id_usuario']))

       categoria = cursor.fetchone()

       if categoria is None:
           flash('Categoria não encontrada!')
           return redirect(url_for('listar_categorias'))

       if id in [1001, 1002]:
           flash('Esta categoria não pode ser editada.')
           return redirect(url_for('listar_categorias'))


       if request.method == 'POST':
           nome_categoria = request.form['nome_categoria']
           nome_categoria.strip().lower()

           if not nome_categoria:
               flash('Informe o nome da categoria!')
               nome = buscarUsuario(session['id_usuario'])[1]
               usuario = buscarUsuario(id)
               caminho = "img/capas/" + str(usuario[0]) + ".jpg"

               return render_template(
                   'editar_categorias.html',
                   id=id,
                   nome=nome,
                   categoria=categoria,
                   img=caminho
               )

           cursor.execute("""
               SELECT 1
               FROM CATEGORIA
               WHERE LOWER(NOME) = ?
                 AND ID_CATEGORIA != ?
           """, (nome_categoria, id))

           if cursor.fetchone() is not None:
               flash('Erro: Categoria já cadastrada!')
               nome = buscarUsuario(session['id_usuario'])[1]
               usuario = buscarUsuario(id)
               caminho = "img/capas/" + str(usuario[0]) + ".jpg"
               return render_template(
                   'editar_categorias.html',
                   id=id,
                   nome=nome,
                   categoria=(nome_categoria, categoria[1]),
                   img=caminho
               )

           cursor.execute("""
               UPDATE CATEGORIA
               SET NOME = ?
               WHERE ID_CATEGORIA = ?
                 AND ID_USUARIO = ?
           """, (
               nome_categoria,
               id,
               session['id_usuario']
           ))

           con.commit()
           flash('Categoria editada com sucesso!')
           return redirect(url_for('listar_categorias'))

       nome = buscarUsuario(session['id_usuario'])[1]
       usuario = buscarUsuario(id)
       caminho = "img/capas/" + str(usuario[0]) + ".jpg"

       return render_template(
           'editar_categorias.html',
           id=id,
           nome=nome,
           categoria=categoria,
           img=caminho
       )

   except Exception as e:
       con.rollback()
       flash(f'Ocorreu um erro: {e}')
       return redirect(url_for('listar_categorias'))

   finally:
       cursor.close()


@app.route('/listar_categorias', methods=['GET', 'POST'])
def listar_categorias():
    if 'id_usuario' not in session:
        flash('Precisa estar logado')
        return redirect(url_for('login'))

    banco = """SELECT ID_CATEGORIA, NOME, STATUS
                   FROM CATEGORIA
                   WHERE ID_USUARIO = ?"""

    parametros = [session['id_usuario']]

    if request.method == 'POST':
        nome_categoria = request.form['nome_categoria'].strip().lower()

        if nome_categoria:
            banco += " AND LOWER(NOME) LIKE ?"
            parametros.append(nome_categoria)

    cursor = con.cursor()
    cursor.execute(banco, parametros)
    categorias = cursor.fetchall()
    cursor.close()

    nome = session['nome']
    usuario = buscarUsuario(id)
    caminho = "img/capas/" + str(usuario[0]) + ".jpg"
    return render_template('listar_categorias.html', categorias=categorias, nome=nome, img=caminho)



@app.route('/alterar_status_categoria/<int:id>', methods=['POST'])
def alterar_status_categoria(id):
    if 'id_usuario' not in session:
        flash('Precisa estar logado')
        return redirect(url_for('login'))

    else:
        cursor = con.cursor()
        cursor.execute("""SELECT STATUS FROM CATEGORIA WHERE ID_CATEGORIA = ? AND ID_USUARIO = ?""", (id, session['id_usuario']))
        status = cursor.fetchone()[0]

        try:

            if status == 0:
                cursor.execute("""UPDATE CATEGORIA SET STATUS = 1 WHERE ID_CATEGORIA = ?""", (id,))
                con.commit()
                flash('Status alterado com sucesso!')

            elif status == 1:
                cursor.execute("""UPDATE CATEGORIA SET STATUS = 0 WHERE ID_CATEGORIA = ?""", (id,))
                con.commit()
                flash('Status alterado com sucesso!')

            return redirect(url_for('listar_categorias'))

        except Exception as e:
            con.rollback()
            flash(f'Ocorreu um erro -> {e}')
            return redirect(url_for('listar_categorias'))

        finally:
            cursor.close()

if __name__ == '__main__':
    app.run(debug=True)